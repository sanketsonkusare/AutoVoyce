"""Answer a question about the selected videos with one streamed model call."""

import asyncio
import logging
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from settings import GOOGLE_API_KEY, QUERY_MODEL, QUERY_THINKING_BUDGET
from src.rag import history
from src.rag.prompt import SYSTEM_PROMPT, build_user_message
from src.rag.retrieval import search_passages

logger = logging.getLogger("autovoyce.answer")

SEARCH_ERROR_MESSAGE = "Couldn't search your videos. Please try again."
ANSWER_ERROR_MESSAGE = "The answer couldn't be completed. Please try again."
MODEL_TIMEOUT_SECONDS = 60


class AnswerError(Exception):
    """The answer failed; the message is safe to show to the user."""


def get_model():
    return ChatGoogleGenerativeAI(
        model=QUERY_MODEL,
        api_key=GOOGLE_API_KEY,
        thinking_budget=QUERY_THINKING_BUDGET,
        timeout=MODEL_TIMEOUT_SECONDS,
        # One attempt only: the library default (6 attempts) would turn the
        # 60 s limit into several minutes of waiting.
        max_retries=1,
    )


def _chunk_text(content) -> str:
    """Gemini streams content as a string or as a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) and block.get("type") == "text"
            else block if isinstance(block, str) else ""
            for block in content
        )
    return ""


async def stream_answer(
    session_id: str, namespace: str, question: str, executor=None
) -> AsyncIterator[dict]:
    """
    Yield the answer as events: one "sources", then "token"s, then "done".
    On failure yields one "error" event and stops. The exchange is saved to the
    chat history only when the answer completes (never on error or disconnect).
    """
    past = history.get_history(session_id)
    previous_question = past[-1][0] if past else None

    loop = asyncio.get_running_loop()
    try:
        passages = await loop.run_in_executor(
            executor, search_passages, namespace, question, previous_question
        )
    except Exception:
        logger.error(f"Search failed for session {session_id}", exc_info=True)
        yield {"type": "error", "message": SEARCH_ERROR_MESSAGE}
        return

    yield {"type": "sources", "sources": [p.to_dict() for p in passages]}

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for past_question, past_answer in past:
        messages.append(HumanMessage(content=past_question))
        messages.append(AIMessage(content=past_answer))
    messages.append(HumanMessage(content=build_user_message(question, passages)))

    parts: list[str] = []
    try:
        async for chunk in get_model().astream(messages):
            text = _chunk_text(chunk.content)
            if text:
                parts.append(text)
                yield {"type": "token", "text": text}
    except Exception:
        logger.error(f"Answer generation failed for session {session_id}", exc_info=True)
        yield {"type": "error", "message": ANSWER_ERROR_MESSAGE}
        return

    # The answer is complete: save it before "done" so a consumer that stops
    # reading at "done" still records the exchange.
    full_answer = "".join(parts)
    if not full_answer.strip():
        # Gemini can stop without text (e.g. SAFETY or RECITATION) and no error
        logger.warning(f"Empty answer from the model for session {session_id}")
        yield {"type": "error", "message": ANSWER_ERROR_MESSAGE}
        return
    history.add_exchange(session_id, question, full_answer)
    yield {"type": "done", "answer": full_answer}


async def answer(session_id: str, namespace: str, question: str, executor=None) -> dict:
    """Non-streaming version: returns {"response", "sources"} or raises AnswerError."""
    sources: list[dict] = []
    async for event in stream_answer(session_id, namespace, question, executor):
        if event["type"] == "sources":
            sources = event["sources"]
        elif event["type"] == "error":
            raise AnswerError(event["message"])
        elif event["type"] == "done":
            return {"response": event["answer"], "sources": sources}
    raise AnswerError(ANSWER_ERROR_MESSAGE)

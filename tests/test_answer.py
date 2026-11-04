import pytest

from src.rag import answer as answer_module
from src.rag import history
from src.rag.answer import (
    ANSWER_ERROR_MESSAGE, SEARCH_ERROR_MESSAGE, AnswerError, answer, stream_answer,
)
from src.rag.prompt import SYSTEM_PROMPT
from src.rag.retrieval import Passage
from tests.fakes import FakeChatModel

PASSAGE = Passage(1, "abcdefghijk", "T", "C", 272, "battery is good", "https://www.youtube.com/watch?v=abcdefghijk&t=272s")


async def collect(gen):
    return [e async for e in gen]


@pytest.fixture(autouse=True)
def clean_history():
    history.clear("s")
    yield
    history.clear("s")


@pytest.fixture
def search_calls(monkeypatch):
    calls = []

    def fake_search(namespace, question, previous_question=None):
        calls.append((namespace, question, previous_question))
        return [PASSAGE]

    monkeypatch.setattr(answer_module, "search_passages", fake_search)
    return calls


def use_model(monkeypatch, chunks, fail_after=None):
    model = FakeChatModel(chunks=chunks, fail_after=fail_after, calls=[])
    monkeypatch.setattr(answer_module, "get_model", lambda: model)
    return model


async def test_event_order_and_history_saved(search_calls, monkeypatch):
    use_model(monkeypatch, ["Good ", "[1]."])
    events = await collect(stream_answer("s", "ns", "battery?"))
    assert [e["type"] for e in events] == ["sources", "token", "token", "done"]
    assert events[0]["sources"] == [PASSAGE.to_dict()]
    assert events[-1]["answer"] == "Good [1]."
    assert history.get_history("s")[-1] == ("battery?", "Good.")


async def test_model_gets_system_history_and_passages(search_calls, monkeypatch):
    model = use_model(monkeypatch, ["ok"])
    history.add_exchange("s", "earlier q", "earlier a")
    await collect(stream_answer("s", "ns", "now?"))
    msgs = model.calls[0]
    assert msgs[0].content == SYSTEM_PROMPT
    assert [m.content for m in msgs[1:3]] == ["earlier q", "earlier a"]
    assert "Question: now?" in msgs[-1].content and "battery is good" in msgs[-1].content
    assert search_calls[-1] == ("ns", "now?", "earlier q")


async def test_gemini_block_lists_are_flattened(search_calls, monkeypatch):
    use_model(monkeypatch, [[{"type": "text", "text": "Hi"}]])
    events = await collect(stream_answer("s", "ns", "q"))
    assert events[-1] == {"type": "done", "answer": "Hi"}


async def test_empty_sources_still_answers(monkeypatch):
    monkeypatch.setattr(answer_module, "search_passages", lambda *a, **k: [])
    model = use_model(monkeypatch, ["The selected videos don't cover this, but..."])
    events = await collect(stream_answer("s", "ns", "q"))
    assert events[0] == {"type": "sources", "sources": []}
    assert events[-1]["type"] == "done"
    assert "No passages" in model.calls[0][-1].content


async def test_search_failure_yields_error_only(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("pinecone down")

    monkeypatch.setattr(answer_module, "search_passages", boom)
    use_model(monkeypatch, ["x"])
    assert await collect(stream_answer("s", "ns", "q")) == [
        {"type": "error", "message": SEARCH_ERROR_MESSAGE}]


async def test_model_failure_after_tokens(search_calls, monkeypatch):
    use_model(monkeypatch, ["Good ", "more"], fail_after=1)
    events = await collect(stream_answer("s", "ns", "q"))
    assert [e["type"] for e in events] == ["sources", "token", "error"]
    assert events[-1]["message"] == ANSWER_ERROR_MESSAGE
    assert history.get_history("s") == []


async def test_disconnect_does_not_save_history(search_calls, monkeypatch):
    use_model(monkeypatch, ["a", "b", "c"])
    gen = stream_answer("s", "ns", "q")
    await gen.__anext__()  # sources
    await gen.__anext__()  # first token
    await gen.aclose()
    assert history.get_history("s") == []


async def test_answer_collects(search_calls, monkeypatch):
    use_model(monkeypatch, ["Good ", "[1]."])
    assert await answer("s", "ns", "q") == {"response": "Good [1].", "sources": [PASSAGE.to_dict()]}


async def test_answer_raises_on_error(monkeypatch):
    monkeypatch.setattr(answer_module, "search_passages",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(AnswerError, match="Couldn't search"):
        await answer("s", "ns", "q")


async def test_answer_saves_history(search_calls, monkeypatch):
    use_model(monkeypatch, ["Good ", "[1]."])
    await answer("s", "ns", "q")
    assert history.get_history("s") == [("q", "Good.")]

from langchain_core.messages import HumanMessage, SystemMessage
from src.tools.query_tool import query_tool
from langchain_google_genai import ChatGoogleGenerativeAI
from settings import GOOGLE_API_KEY
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from pathlib import Path
import yaml


PROMPTS_PATH = Path(__file__).resolve().parent.parent / "utils" / "promps.yml"
with open(PROMPTS_PATH, "r") as f:
    PROMPTS = yaml.safe_load(f)

# --- Module-level shared checkpointer (in-memory, survives across requests) ---
# For production multi-instance deployments, swap with SqliteSaver or PostgresSaver.
_checkpointer = MemorySaver()

# Cache compiled agents per namespace so we don't recreate the graph on every call
_agent_cache: dict = {}


def _get_or_create_agent(namespace: str, verbose: bool):
    """Return a cached compiled agent graph for the given namespace, creating it if needed."""
    if namespace in _agent_cache:
        return _agent_cache[namespace]

    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=GOOGLE_API_KEY, verbose=verbose)

    system_prompt_text = PROMPTS.get("query_agent_prompt", "You are a helpful assistant.")
    system_prompt = SystemMessage(content=system_prompt_text)

    from langchain.tools import tool

    # We need a closure to capture the namespace
    @tool
    def search_knowledge_base(query: str) -> str:
        """Searches the knowledge base for relevant context about the uploaded videos."""
        return query_tool.func(query=query, namespace=namespace)

    agent = create_agent(
        model,
        tools=[search_knowledge_base],
        system_prompt=system_prompt,
        checkpointer=_checkpointer,
    )

    _agent_cache[namespace] = agent
    return agent


def query_agent(query: str, namespace: str, session_id: str, verbose: bool = True) -> str:
    """
    Agent that takes a query, searches Pinecone for context, and answers the question.
    Uses MemorySaver checkpointing so that conversation history is retained within a session.

    Args:
        query:      The user's question
        namespace:  The Pinecone namespace to search in
        session_id: The session ID, used as the LangGraph thread_id for memory isolation
        verbose:    Enable verbose logging (default: True)
    """
    agent = _get_or_create_agent(namespace, verbose)

    # Each session_id maps to an isolated conversation thread
    config = {"configurable": {"thread_id": session_id}}

    print(f"🔍 Processing query: {query} [session={session_id}, namespace={namespace}]")
    try:
        result = agent.invoke(
            {"messages": [HumanMessage(content=query)]},
            config,
        )
        response_content = result["messages"][-1].content

        # Parse structured response if it's a list (common with Gemini/Flash models)
        if isinstance(response_content, list):
            text_blocks = [
                block.get("text", "")
                for block in response_content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if text_blocks:
                response = " ".join(text_blocks)
            else:
                response = " ".join(str(item) for item in response_content)
        else:
            response = str(response_content)

        print(f"✅ Query completed successfully")
    except Exception as e:
        response = f"Error processing query: {str(e)}"
        print(f"❌ Query failed: {e}")
        import traceback
        traceback.print_exc()

    return response


if __name__ == "__main__":
    test_query = "Which is the best iphone for students?"
    # For standalone testing, use a dummy session/namespace
    print(query_agent(test_query, namespace="test-ns", session_id="test-session"))

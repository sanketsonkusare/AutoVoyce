from langchain_core.messages import HumanMessage, SystemMessage
from src.tools.query_tool import query_tool
from langchain_google_genai import ChatGoogleGenerativeAI
from settings import GOOGLE_API_KEY
from langchain.agents import create_agent
from pathlib import Path
import yaml


PROMPTS_PATH = Path(__file__).resolve().parent.parent / "utils" / "promps.yml"
with open(PROMPTS_PATH, "r") as f:
    PROMPTS = yaml.safe_load(f)

def query_agent(query: str, namespace: str, verbose: bool = True) -> str:
    """
    Agent that takes a query, searches Pinecone for context, and answers the question.
    Uses langgraph.prebuilt.create_agent for robust tool calling.
    
    Args:
        query: The user's question
        namespace: The Pinecone namespace to search in
        verbose: Enable verbose logging (default: True)
    """
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=GOOGLE_API_KEY, verbose=verbose)
    
    system_prompt_text = PROMPTS.get("query_agent_prompt", "You are a helpful assistant.")
    system_prompt = SystemMessage(content=system_prompt_text)
    
    # Create a wrapper tool that has the namespace bound to it
    from langchain.tools import tool
    
    @tool
    def search_knowledge_base(query: str) -> str:
        """Searches the knowledge base for relevant context."""
        # Force the usage of the passed namespace
        return query_tool.func(query=query, namespace=namespace)
    
    agent = create_agent(model, tools=[search_knowledge_base], system_prompt=system_prompt)
    
    print(f"🔍 Processing query: {query}")
    try:
        result = agent.invoke({
            "messages": [HumanMessage(content=query)]
        })
        response_content = result["messages"][-1].content
        
        # Parse structured response if it's a list (common with Gemini/Flash models)
        if isinstance(response_content, list):
            # Look for text block
            text_blocks = [block.get("text", "") for block in response_content if isinstance(block, dict) and block.get("type") == "text"]
            if text_blocks:
                response = " ".join(text_blocks)
            else:
                # Fallback: join string representations
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
    print(query_agent(test_query))

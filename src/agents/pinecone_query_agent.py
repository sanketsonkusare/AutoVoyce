from langchain_core.messages import HumanMessage, SystemMessage
from src.tools.query_tool import query_tool
from langchain_groq import ChatGroq
from settings import GROQ_API_KEY
from langchain.agents import create_agent
from pathlib import Path
import yaml


PROMPTS_PATH = Path(__file__).resolve().parent.parent / "utils" / "promps.yml"
with open(PROMPTS_PATH, "r") as f:
    PROMPTS = yaml.safe_load(f)

def query_agent(query: str) -> dict:
    """
    Agent that takes a query, searches Pinecone for context, and answers the question.
    Uses langgraph.prebuilt.create_react_agent for robust tool calling with Groq.
    """
    model = ChatGroq(model="llama-3.1-8b-instant", api_key=GROQ_API_KEY)
    
    system_prompt_text = PROMPTS.get("query_agent_prompt", "You are a helpful assistant.")
    system_prompt = SystemMessage(content=system_prompt_text)
    
    agent = create_agent(model, tools=[query_tool], system_prompt=system_prompt)
    
    print(f"Processing query: {query}")
    try:
        result = agent.invoke({
            "messages": [HumanMessage(content=query)]
        })
        response = result["messages"][-1].content
    except Exception as e:
        response = f"Error processing query: {str(e)}"
        import traceback
        traceback.print_exc()
        
    return response

if __name__ == "__main__":
    test_query = "Which is the best iphone for students?"
    print(query_agent(test_query))

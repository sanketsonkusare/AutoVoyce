from langchain_core.messages import HumanMessage
from src.tools.youtube_search import youtube_query
from src.schemas.response_schema import ResponseSchema
from src.agents.agent_creator import create_agent_with_tools
from settings import SEARCH_LIMIT
import re


def retriever_agent(state: ResponseSchema) -> dict:
    query = state["user_query"]
    print(f"Searching for videos with query: '{query}'...")
    
    agent = create_agent_with_tools("retriever_agent", [youtube_query])

    result = agent.invoke({
        "messages": [HumanMessage(content=query)]
    })

    content = result["messages"][-1].content
    matches = re.findall(r"v=([a-zA-Z0-9_-]+)", content)
    
    video_ids = []
    if matches: 
        video_ids = list(dict.fromkeys(matches))
    else:
        print(f"No video IDs found in content: {content}")
        video_ids = []

    top_ids = video_ids[:SEARCH_LIMIT]
    return {"video_ids": top_ids}

if __name__ == "__main__":
    print(retriever_agent({"user_query": "What are some of the best Avengers movies?", "video_ids": [], "transcript": ""}))

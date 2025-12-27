from langchain_core.messages import HumanMessage
from src.tools.youtube_search import youtube_query, youtube_search_with_metadata
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

    # Extract content from result - handle both string and list responses
    content = result.get("messages", [])[-1].content if result.get("messages") else ""
    
    # If content is a list, join it into a string
    if isinstance(content, list):
        content = " ".join(str(item) for item in content)
    
    matches = re.findall(r"v=([a-zA-Z0-9_-]+)", content)
    
    video_ids = []
    if matches: 
        video_ids = list(dict.fromkeys(matches))
    else:
        print(f"No video IDs found in content: {content}")
        video_ids = []

    top_ids = video_ids[:SEARCH_LIMIT]
    return {"video_ids": top_ids}


def retriever_agent_with_metadata(query: str) -> list[dict]:
    """
    Searches YouTube and returns video metadata for user selection.
    Returns list of video dictionaries with id, title, channel, thumbnail, etc.
    """
    print(f"Searching for videos with query: '{query}'...")
    
    videos = youtube_search_with_metadata(query)
    
    # Limit to SEARCH_LIMIT
    limited_videos = videos[:SEARCH_LIMIT]
    
    print(f"Found {len(limited_videos)} videos")
    return limited_videos


if __name__ == "__main__":
    print(retriever_agent({"user_query": "What are some of the best Avengers movies?", "video_ids": [], "transcript": ""}))
    print("\n---\n")
    print(retriever_agent_with_metadata("What are some of the best Avengers movies?"))

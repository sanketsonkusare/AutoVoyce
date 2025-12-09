from langchain_google_genai import ChatGoogleGenerativeAI
from src.tools.youtube_search import youtube_query
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from settings import GOOGLE_API_KEY, SEARCH_LIMIT
import re
from src.schemas.response_schema import ResponseSchema

def retriever_agent(state: ResponseSchema) -> dict:
    query = state["user_query"]
    print(f"Searching for videos with query: '{query}'...")
    
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)
    agent = create_agent(
        model=model,
        tools=[youtube_query],
        system_prompt="""You are a helpful assistant specialized in finding YouTube videos.
    
    ### Instructions:
    1. **Tool Usage**: ALWAYS use the `youtube_query` tool to search for videos.
    2. **Output**: Return the links of the videos in a list format."""
    )

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

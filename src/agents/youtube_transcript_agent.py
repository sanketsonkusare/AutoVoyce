from langchain_google_genai import ChatGoogleGenerativeAI
from src.tools.transcript_fetcher import transcript_fetcher
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from settings import GOOGLE_API_KEY


def transcript_agent(video_id: str):
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GOOGLE_API_KEY)
    agent = create_agent(
        model=model,
        tools=[transcript_fetcher],
        system_prompt="""You are a helpful assistant specialized giving transcripts of YouTube videos.
    
        ### Instructions:
        1. **Tool Usage**: ALWAYS use the `transcript_fetcher` tool to fetch the transcript of a video.
        2. **Output**: Return the transcript of the video in meaningful way."""
    )

    result = agent.invoke({
        "messages": [HumanMessage(content=f"Fetch the transcript for the YouTube video with ID: {video_id}")]
    })

    content = result["messages"][-1].content

    return content


if __name__ == "__main__":
    print(transcript_agent("R1LE5xfasmw"))

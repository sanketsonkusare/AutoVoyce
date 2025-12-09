from langchain_google_genai import ChatGoogleGenerativeAI
from src.tools.transcript_fetcher import transcript_fetcher
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from settings import GOOGLE_API_KEY
from src.schemas.response_schema import ResponseSchema

def transcript_agent(state: ResponseSchema) -> dict:
    video_ids = state["video_ids"]
    print(f"Found {len(video_ids)} videos to process.")
    
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)
    agent = create_agent(
        model=model,
        tools=[transcript_fetcher],
        system_prompt="""You are a helpful assistant specialized giving transcripts of YouTube videos.
    
        ### Instructions:
        1. **Tool Usage**: ALWAYS use the `transcript_fetcher` tool to fetch the transcript of a video.
        2. **Output**: Return the transcript of the video in meaningful way."""
    )

    aggregated_transcripts = ""
    for i, video_id in enumerate(video_ids):
        print(f"Processing video {i+1}/{len(video_ids)}: {video_id}")
        try:
            result = agent.invoke({
                "messages": [HumanMessage(content=f"Fetch the transcript for the YouTube video with ID: {video_id}")]
            })
            transcript = result["messages"][-1].content
            aggregated_transcripts += f"\n\nTranscript for Video ID-{video_id}: \n{transcript}"
        except Exception as e:
            aggregated_transcripts += f"\n\nError for Video ID-{video_id}: \n{str(e)}"
    
    return {"transcript": aggregated_transcripts}

if __name__ == "__main__":
    print(transcript_agent({"user_query": "", "video_ids": ["R1LE5xfasmw"], "transcript": ""}))

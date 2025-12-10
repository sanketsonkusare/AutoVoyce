from langchain_core.messages import HumanMessage
from src.tools.transcript_fetcher import transcript_fetcher
from src.schemas.response_schema import ResponseSchema
from src.agents.agent_creator import create_agent_with_tools

def transcript_agent(state: ResponseSchema) -> dict:
    video_ids = state["video_ids"]
    print(f"Found {len(video_ids)} videos to process.")
    
    agent = create_agent_with_tools("transcript_agent", [transcript_fetcher])

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

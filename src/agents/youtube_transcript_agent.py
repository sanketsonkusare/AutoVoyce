from langchain_core.messages import HumanMessage
from src.tools.transcript_fetcher import transcript_fetcher
from src.schemas.response_schema import ResponseSchema
from src.agents.agent_creator import create_agent_with_tools
from src.utils.event_emitter import event_emitter

def transcript_agent(state: ResponseSchema) -> dict:
    video_ids = state["video_ids"]
    session_id = state.get("session_id", "")
    print(f"Found {len(video_ids)} videos to process.")
    
    if session_id:
        event_emitter.emit(session_id, "transcript_started", f"Starting transcript extraction for {len(video_ids)} videos")
    
    agent = create_agent_with_tools("transcript_agent", [transcript_fetcher])

    aggregated_transcripts = ""
    for i, video_id in enumerate(video_ids):
        print(f"Processing video {i+1}/{len(video_ids)}: {video_id}")
        if session_id:
            event_emitter.emit(session_id, "video_processing", f"Processing video {i+1}/{len(video_ids)}: {video_id}", {
                "video_id": video_id,
                "video_number": i + 1,
                "total_videos": len(video_ids)
            })
        try:
            result = agent.invoke({
                "messages": [HumanMessage(content=f"Fetch the transcript for the YouTube video with ID: {video_id}")]
            })
            transcript = result["messages"][-1].content
            aggregated_transcripts += f"\n\nTranscript for Video ID-{video_id}: \n{transcript}"
            if session_id:
                event_emitter.emit(session_id, "video_processed", f"Video {i+1}/{len(video_ids)} processed successfully", {
                    "video_id": video_id,
                    "video_number": i + 1,
                    "total_videos": len(video_ids)
                })
        except Exception as e:
            aggregated_transcripts += f"\n\nError for Video ID-{video_id}: \n{str(e)}"
            if session_id:
                event_emitter.emit(session_id, "video_error", f"Error processing video {i+1}/{len(video_ids)}: {str(e)}", {
                    "video_id": video_id,
                    "video_number": i + 1,
                    "total_videos": len(video_ids),
                    "error": str(e)
                })
    
    if session_id:
        event_emitter.emit(session_id, "transcript_complete", f"Transcript extraction completed for {len(video_ids)} videos")
    
    return {"transcript": aggregated_transcripts}

if __name__ == "__main__":
    print(transcript_agent({"user_query": "", "video_ids": ["R1LE5xfasmw"], "transcript": ""}))

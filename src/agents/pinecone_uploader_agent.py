from langchain_core.messages import HumanMessage
from src.tools.pinecone_uploader import upload_transcript_to_pinecone
from src.schemas.response_schema import ResponseSchema
from src.agents.agent_creator import create_agent_with_tools
from src.utils.event_emitter import event_emitter

def uploader_agent(state: ResponseSchema) -> dict:
    transcript = state.get("transcript", "")
    namespace = state.get("namespace", "youtube_transcripts")  # Get namespace from state
    session_id = state.get("session_id", "")
    
    if not transcript:
        return {"transcript": "No transcript provided."}

    print(f"Processing transcript upload to namespace: {namespace}...")
    if session_id:
        event_emitter.emit(session_id, "pinecone_upload_started", f"Starting Pinecone upload to namespace: {namespace}")
    try:
        # Call the tool directly with namespace and session_id for event emission
        response = upload_transcript_to_pinecone.invoke({
            "transcript": transcript,
            "namespace": namespace,
            "session_id": session_id
        })
        if session_id:
            event_emitter.emit(session_id, "pinecone_upload_complete", f"Successfully uploaded to Pinecone namespace: {namespace}")
    except Exception as e:
        response = f"Error during upload: {str(e)}"
        if session_id:
            event_emitter.emit(session_id, "pinecone_upload_error", f"Error uploading to Pinecone: {str(e)}", {
                "error": str(e)
            })
        import traceback
        traceback.print_exc()
    
    return {"transcript": transcript, "query_response": response}

if __name__ == "__main__":
    # Test with dummy data
    test_transcript = "This sanket is a test transcript.\n" * 10
    print(uploader_agent({"user_query": "test", "video_ids": [], "transcript": test_transcript}))

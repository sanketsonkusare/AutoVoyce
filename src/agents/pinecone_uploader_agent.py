from src.tools.pinecone_uploader import upload_transcripts
from src.schemas.response_schema import ResponseSchema
from src.utils.event_emitter import event_emitter
import logging

logger = logging.getLogger("autovoyce.uploader_agent")


def uploader_agent(state: ResponseSchema) -> dict:
    transcripts = state.get("transcripts", [])
    namespace = state.get("namespace", "youtube_transcripts")
    session_id = state.get("session_id", "")

    if not transcripts:
        return {"query_response": "No transcript provided."}

    logger.info(f"Uploading {len(transcripts)} transcripts to namespace: {namespace}")
    try:
        count = upload_transcripts(transcripts, namespace, session_id)
        response = f"Uploaded {count} chunks to Pinecone namespace '{namespace}'."
        if session_id:
            event_emitter.emit(session_id, "pinecone_upload_complete", f"Successfully uploaded to Pinecone namespace: {namespace}")
    except Exception as e:
        response = f"Error during upload: {str(e)}"
        logger.error(response, exc_info=True)
        if session_id:
            event_emitter.emit(session_id, "pinecone_upload_error", f"Error uploading to Pinecone: {str(e)}", {
                "error": str(e)
            })

    return {"query_response": response}

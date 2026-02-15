from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone
from settings import PINECONE_API_KEY, PINECONE_INDEX_NAME, PINECONE_HOST_URL
from src.utils.event_emitter import event_emitter
from langchain.tools import tool
import uuid
import logging
import time

logger = logging.getLogger("autovoyce.uploader")

# Max records per upsert_records batch (Pinecone integrated inference limit)
_BATCH_SIZE = 96


@tool
def upload_transcript_to_pinecone(transcript: str, namespace: str = "youtube_transcripts", session_id: str = "") -> str:
    """
    Uploads a YouTube transcript to the Pinecone vector database.
    Uses Pinecone integrated inference — embeddings are generated server-side.
    
    Args:
        transcript: The transcript text to upload
        namespace: The Pinecone namespace to use for isolation (default: "youtube_transcripts")
        session_id: Optional session ID for event emission
    """
    print("Starting Pinecone upload process...")
    if session_id:
        event_emitter.emit(session_id, "pinecone_upload_started", "Starting Pinecone upload process...")
    
    if not transcript:
        print("No transcript to upload.")
        return "No transcript found to upload."

    try:
        # Initialize Pinecone index
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(host=PINECONE_HOST_URL)

        # Chunk the transcript using RecursiveCharacterTextSplitter
        # (no local embeddings needed — Pinecone handles embedding server-side)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        
        if session_id:
            event_emitter.emit(session_id, "chunking_text", "Splitting transcript into chunks...")
        
        chunks = splitter.split_text(transcript)
        
        if not chunks:
            return "No text chunks to upload."

        # Build records for Pinecone integrated inference
        # Each record has an _id and chunk_text (auto-embedded by Pinecone)
        records = []
        for i, chunk_text in enumerate(chunks):
            records.append({
                "_id": str(uuid.uuid4()),
                "chunk_text": chunk_text,
                "chunk_id": i,
                "source": "uploaded_document",
            })

        # Upsert in batches of _BATCH_SIZE (Pinecone integrated inference limit)
        print(f"Uploading transcript to Pinecone (Namespace: {namespace})...")
        if session_id:
            event_emitter.emit(session_id, "pinecone_uploading", f"Uploading {len(records)} chunks to Pinecone (Namespace: {namespace})...")
        
        total_uploaded = 0
        for batch_start in range(0, len(records), _BATCH_SIZE):
            batch = records[batch_start : batch_start + _BATCH_SIZE]
            index.upsert_records(namespace, batch)
            total_uploaded += len(batch)
            logger.info(f"Uploaded batch {batch_start // _BATCH_SIZE + 1}: {len(batch)} records")

        # Small delay to let Pinecone index the records
        time.sleep(2)

        success_msg = f"Uploaded {total_uploaded} chunks to Pinecone index '{PINECONE_INDEX_NAME}' in namespace '{namespace}'"
        print(success_msg)
        
        if session_id:
            event_emitter.emit(session_id, "chunks_uploaded", success_msg, {
                "chunk_count": total_uploaded,
                "namespace": namespace
            })
        
        return f"Transcript successfully uploaded to Pinecone namespace '{namespace}'."
        
    except Exception as e:
        error_msg = f"Error uploading to Pinecone: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg


if __name__ == "__main__":
    # Test execution
    mock_transcript = "This is a test transcript for Pinecone upload verification.\n" * 50
    print(upload_transcript_to_pinecone.invoke({"transcript": mock_transcript}))
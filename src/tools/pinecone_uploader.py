from pinecone import Pinecone
from settings import PINECONE_API_KEY, PINECONE_INDEX_NAME, PINECONE_HOST_URL
from src.schemas.response_schema import VideoTranscript
from src.tools.chunking import chunk_segments
from src.utils.event_emitter import event_emitter
import logging
import time

logger = logging.getLogger("autovoyce.uploader")

# Max records per upsert_records batch (Pinecone integrated inference limit)
_BATCH_SIZE = 96

# Seconds to wait after upserting so Pinecone can index the records
_INDEX_SETTLE_SECONDS = 2


def _get_index():
    return Pinecone(api_key=PINECONE_API_KEY).Index(host=PINECONE_HOST_URL)


def build_records(transcript: VideoTranscript) -> list[dict]:
    """
    Turn one video's transcript into Pinecone records.
    Pinecone embeds chunk_text server-side (integrated inference).
    start_seconds is -1 when the time is unknown (Pinecone fields can't be null).
    """
    video_id = transcript["video_id"]
    return [
        {
            "_id": f"{video_id}-{i}",
            "chunk_text": chunk["text"],
            "video_id": video_id,
            "title": transcript["title"],
            "channel": transcript["channel"],
            "start_seconds": int(chunk["start"]) if chunk["start"] is not None else -1,
        }
        for i, chunk in enumerate(chunk_segments(transcript["segments"]))
    ]


def upload_transcripts(
    transcripts: list[VideoTranscript], namespace: str, session_id: str = ""
) -> int:
    """Chunk each video's transcript and upload it. Returns the number of chunks."""
    if session_id:
        event_emitter.emit(session_id, "pinecone_upload_started", "Starting Pinecone upload process...")
        event_emitter.emit(session_id, "chunking_text", "Splitting transcript into chunks...")

    records = [record for t in transcripts for record in build_records(t)]
    if not records:
        return 0

    if session_id:
        event_emitter.emit(
            session_id, "pinecone_uploading",
            f"Uploading {len(records)} chunks to Pinecone (Namespace: {namespace})...",
        )

    index = _get_index()
    for batch_start in range(0, len(records), _BATCH_SIZE):
        batch = records[batch_start : batch_start + _BATCH_SIZE]
        index.upsert_records(namespace=namespace, records=batch)
        logger.info(f"Uploaded batch {batch_start // _BATCH_SIZE + 1}: {len(batch)} records")

    # Small delay to let Pinecone index the records
    time.sleep(_INDEX_SETTLE_SECONDS)

    msg = f"Uploaded {len(records)} chunks to Pinecone index '{PINECONE_INDEX_NAME}' in namespace '{namespace}'"
    logger.info(msg)
    if session_id:
        event_emitter.emit(session_id, "chunks_uploaded", msg, {
            "chunk_count": len(records),
            "namespace": namespace,
        })
    return len(records)

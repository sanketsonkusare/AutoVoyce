from src.tools.transcript_fetcher import get_transcript_from_api, transcript_text
from src.schemas.response_schema import ResponseSchema, VideoTranscript
from src.utils.event_emitter import event_emitter
import logging

logger = logging.getLogger("autovoyce.transcript_agent")


def transcript_agent(state: ResponseSchema) -> dict:
    videos = state.get("videos", [])
    session_id = state.get("session_id", "")
    total = len(videos)
    logger.info(f"Found {total} videos to process.")

    def emit(event_type: str, message: str, data: dict | None = None):
        if session_id:
            event_emitter.emit(session_id, event_type, message, data)

    emit("transcript_started", f"Starting transcript extraction for {total} videos")

    transcripts: list[VideoTranscript] = []
    for i, video in enumerate(videos):
        video_url = f"https://www.youtube.com/watch?v={video['id']}"
        position = {"video_url": video_url, "video_number": i + 1, "total_videos": total}
        logger.info(f"Processing video {i + 1}/{total}: {video_url}")
        emit("video_processing", f"Processing video {i + 1}/{total}: {video_url}", position)

        try:
            segments = get_transcript_from_api(video["id"])
        except Exception as e:
            logger.warning(f"Transcript fetch failed for {video_url}: {e}")
            emit(
                "video_error",
                f"Failed to fetch transcript for video {i + 1}/{total}: {video_url}",
                {**position, "error": f"Error: Could not get transcript. {e}"},
            )
            continue

        if not transcript_text(segments).strip():
            error_msg = (
                f"Empty transcript returned for video {video_url}. "
                "The video might be silent, too short, or have audio issues."
            )
            logger.warning(error_msg)
            emit(
                "video_error",
                f"Empty transcript for video {i + 1}/{total}: {video_url}",
                {**position, "error": error_msg},
            )
            continue

        transcripts.append({
            "video_id": video["id"],
            "title": video["title"],
            "channel": video["channel"],
            "segments": segments,
        })
        emit("video_processed", f"Video {i + 1}/{total} processed successfully", position)

    emit("transcript_complete", f"Transcript extraction completed for {total} videos")
    return {"transcripts": transcripts}

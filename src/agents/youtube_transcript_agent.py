from src.tools.transcript_fetcher import transcript_fetcher
from src.schemas.response_schema import ResponseSchema
from src.utils.event_emitter import event_emitter
import logging

logger = logging.getLogger("autovoyce.transcript_agent")


def transcript_agent(state: ResponseSchema) -> dict:
    video_urls = state["video_urls"]
    session_id = state.get("session_id", "")
    print(f"Found {len(video_urls)} videos to process.")

    if session_id:
        event_emitter.emit(
            session_id,
            "transcript_started",
            f"Starting transcript extraction for {len(video_urls)} videos",
        )

    aggregated_transcripts = ""
    for i, video_url in enumerate(video_urls):
        print(f"Processing video {i + 1}/{len(video_urls)}: {video_url}")
        if session_id:
            event_emitter.emit(
                session_id,
                "video_processing",
                f"Processing video {i + 1}/{len(video_urls)}: {video_url}",
                {
                    "video_url": video_url,
                    "video_number": i + 1,
                    "total_videos": len(video_urls),
                },
            )
        try:
            # Call the tool directly instead of going through the LLM agent
            transcript = transcript_fetcher.invoke({"video_url": video_url})
            logger.info(f"Transcript for video {video_url} fetched by fetcher tool")

            # Handle case where transcript might be a list instead of a string
            if isinstance(transcript, list):
                transcript = " ".join(str(item) for item in transcript if item)

            # Ensure transcript is a string
            if not isinstance(transcript, str):
                transcript = str(transcript) if transcript else ""

            # Handle empty or None transcripts
            if (
                not transcript
                or transcript.strip() == ""
                or transcript.lower() == "none"
            ):
                error_msg = f"Empty transcript returned for video {video_url}. The video might be silent, too short, or have audio issues."
                logger.warning(error_msg)
                if session_id:
                    event_emitter.emit(
                        session_id,
                        "video_error",
                        f"Empty transcript for video {i + 1}/{len(video_urls)}: {video_url}",
                        {
                            "video_url": video_url,
                            "video_number": i + 1,
                            "total_videos": len(video_urls),
                            "error": error_msg,
                        },
                    )
                continue

            # Check if transcript_fetcher returned an error message instead of a real transcript
            if transcript.startswith("Error:"):
                logger.warning(f"Transcript fetcher returned error for {video_url}: {transcript}")
                if session_id:
                    event_emitter.emit(
                        session_id,
                        "video_error",
                        f"Failed to fetch transcript for video {i + 1}/{len(video_urls)}: {video_url}",
                        {
                            "video_url": video_url,
                            "video_number": i + 1,
                            "total_videos": len(video_urls),
                            "error": transcript,
                        },
                    )
                continue

            aggregated_transcripts += (
                f"\n\nTranscript for Video URL-{video_url}: \n{transcript}"
            )
            if session_id:
                event_emitter.emit(
                    session_id,
                    "video_processed",
                    f"Video {i + 1}/{len(video_urls)} processed successfully",
                    {
                        "video_url": video_url,
                        "video_number": i + 1,
                        "total_videos": len(video_urls),
                    },
                )
        except Exception as e:
            logger.error(f"Error processing video {video_url}: {str(e)}")
            if session_id:
                event_emitter.emit(
                    session_id,
                    "video_error",
                    f"Error processing video {i + 1}/{len(video_urls)}: {str(e)}",
                    {
                        "video_url": video_url,
                        "video_number": i + 1,
                        "total_videos": len(video_urls),
                        "error": str(e),
                    },
                )

    if session_id:
        event_emitter.emit(
            session_id,
            "transcript_complete",
            f"Transcript extraction completed for {len(video_urls)} videos",
        )

    return {"transcript": aggregated_transcripts}


if __name__ == "__main__":
    print(
        transcript_agent(
            {
                "user_query": "",
                "video_urls": ["https://www.youtube.com/watch?v=R1LE5xfasmw"],
                "transcript": "",
            }
        )
    )

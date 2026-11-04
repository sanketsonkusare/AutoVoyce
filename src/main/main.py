from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated, Optional, List
from src.workflow.workflow import processing_workflow
from src.rag.answer import AnswerError, answer, stream_answer
from src.agents.youtube_retriever_agent import retriever_agent_with_metadata
from src.utils import session_manager
from src.utils.event_emitter import event_emitter
from settings import DEFAULT_TIMEOUT_SECONDS, SEARCH_LIMIT
from os import getenv
from concurrent.futures import ThreadPoolExecutor
import asyncio
import json
import logging

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("autovoyce")

# --- Shared Thread Pool ---
# Single shared executor for all background processing (bounded to prevent resource leaks)
_background_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="autovoyce-worker")

app = FastAPI(title="AutoVoyce API", version="1.0.0")

# --- CORS ---
ALLOWED_ORIGINS_DEFAULT = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"
ALLOWED_ORIGINS = getenv("ALLOWED_ORIGINS", ALLOWED_ORIGINS_DEFAULT).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request Models ---
# Size limits keep a single request from running up API costs
MAX_QUERY_CHARS = 2000
MAX_TTS_REQUEST_CHARS = 20000
TTS_MAX_SPOKEN_CHARS = 5000

VideoId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{11}$")]


class QueryRequest(BaseModel):
    user_query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    session_id: Optional[str] = None


class ProcessRequest(BaseModel):
    video_ids: List[VideoId] = Field(max_length=SEARCH_LIMIT)
    session_id: Optional[str] = None


class TTSRequest(BaseModel):
    text: str = Field(max_length=MAX_TTS_REQUEST_CHARS)
    voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb"


def _trim_for_tts(text: str) -> str:
    """Keep speech to TTS_MAX_SPOKEN_CHARS, cutting at the last sentence end."""
    if len(text) <= TTS_MAX_SPOKEN_CHARS:
        return text
    cut = text[:TTS_MAX_SPOKEN_CHARS]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("\n"))
    return cut[: end + 1].rstrip() if end > 0 else cut


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return validation errors as one readable string (the frontend shows `detail`)."""
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", []) if p != "body")
        parts.append(f"{field}: {err.get('msg', 'invalid value')}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts) or "Invalid request"})


# --- Health Check ---
@app.get("/")
def read_root():
    return {"message": "AutoVoyce API is running"}


@app.get("/health")
def health_check():
    """Health check endpoint for uptime monitoring and load balancers."""
    return {
        "status": "healthy",
        "active_sessions": len(session_manager.get_all_sessions()),
        "executor_threads": _background_executor._max_workers,
    }


# --- Video Search ---
@app.post("/upload")
async def search_videos(request: QueryRequest):
    """
    Phase 1: Searches YouTube for videos matching the query.
    Creates a new session and returns video list for user selection.
    """
    try:
        # create_session may call Pinecone, so keep it off the event loop
        loop = asyncio.get_running_loop()
        session_id, namespace = await loop.run_in_executor(
            _background_executor, session_manager.create_session
        )

        logger.info(f"Created session {session_id} -> namespace {namespace}")

        # Run blocking search in thread pool to avoid blocking event loop
        videos = await loop.run_in_executor(
            _background_executor, retriever_agent_with_metadata, request.user_query
        )
        session_manager.set_videos(session_id, videos)

        namespace_check = session_manager.get_namespace(session_id)
        if not namespace_check:
            logger.warning(f"Session {session_id} was lost after search!")

        logger.info(f"Search complete for session {session_id}: {len(videos)} videos found")
        return {
            "session_id": session_id,
            "namespace": namespace,
            "status": "search_complete",
            "videos": videos,
            "message": f"Found {len(videos)} videos. Please select which ones to process.",
        }
    except Exception as e:
        logger.error(f"Error in /upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Transcript Fetching ---
@app.get("/transcript/{video_id}")
async def get_transcript(video_id: str):
    """
    Fetch transcript for a single video using youtube-transcript-api.
    Uses Webshare proxy if configured.
    """
    try:
        from src.tools import transcript_fetcher

        logger.info(f"Fetching transcript for video: {video_id}")

        # Run blocking transcript fetch in thread pool
        loop = asyncio.get_running_loop()
        segments = await loop.run_in_executor(
            _background_executor, transcript_fetcher.get_transcript_from_api, video_id
        )
        transcript = transcript_fetcher.transcript_text(segments)

        if not transcript.strip():
            raise HTTPException(status_code=404, detail="No transcript available for this video")

        logger.info(f"Got transcript for {video_id}: {len(transcript)} chars")
        return {
            "transcript": transcript,
            "video_id": video_id,
            "segments": len(segments),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcript fetch failed for {video_id}: {e}")
        if "No captions available" in str(e) or "Transcript is disabled" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# --- Video Processing ---
@app.post("/upload/process")
async def process_selected_videos(
    request: ProcessRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Phase 2: Processes selected videos (transcript extraction + Pinecone upload).
    Runs in background thread; frontend connects to SSE for progress.
    """
    try:
        session_id = request.session_id or x_session_id

        logger.info(f"Process request - session: {session_id}, videos: {len(request.video_ids)}")

        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="No active session. Please search for videos first.",
            )

        session_manager.update_last_access(session_id)
        namespace = session_manager.get_namespace(session_id)

        if not namespace:
            logger.warning(f"Session {session_id} not found. Active: {list(session_manager.get_all_sessions().keys())}")
            raise HTTPException(
                status_code=404,
                detail="Session not found or expired. Please search for videos again.",
            )

        if not request.video_ids:
            raise HTTPException(
                status_code=400,
                detail="No video IDs provided. Please select at least one video.",
            )


        def run_processing_workflow():
            """Background processing: fetch transcripts → embed → upload to Pinecone."""
            logger.info(f"[BG] Processing started for session {session_id}")
            event_emitter.emit(
                session_id,
                "processing_started",
                f"Processing started for {len(request.video_ids)} videos",
            )

            try:
                from dotenv import load_dotenv
                load_dotenv(".env")

                # Titles and channels come from the session's search results
                videos = []
                for vid in request.video_ids:
                    found = session_manager.get_video(session_id, vid) or {}
                    videos.append({
                        "id": vid,
                        "title": found.get("title") or "YouTube video",
                        "channel": found.get("channel") or "",
                    })

                initial_state = {
                    "videos": videos,
                    "namespace": namespace,
                    "session_id": session_id,
                }

                logger.info(f"[BG] Running workflow for session {session_id}, {len(request.video_ids)} videos")
                session_manager.update_last_access(session_id)

                result = processing_workflow.invoke(initial_state)

                logger.info(f"[BG] Workflow completed for session {session_id}")
                event_emitter.emit(
                    session_id,
                    "processing_complete",
                    "All videos processed successfully",
                )
                session_manager.update_last_access(session_id)
                return result

            except Exception as e:
                logger.error(f"[BG] Workflow error for session {session_id}: {e}", exc_info=True)
                event_emitter.emit(
                    session_id,
                    "processing_error",
                    f"Error: {str(e)}",
                )
                raise

        # Submit to shared executor (no per-request executor leak)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(_background_executor, run_processing_workflow)

        def handle_future_result(fut):
            try:
                fut.result()
            except Exception as e:
                logger.error(f"[BG] Background task failed for session {session_id}: {e}")

        future.add_done_callback(handle_future_result)
        logger.info(f"Background task submitted for session {session_id}")

        return {
            "session_id": session_id,
            "namespace": namespace,
            "status": "processing",
            "video_count": len(request.video_ids),
            "message": f"Processing {len(request.video_ids)} selected videos. You can start querying in a few moments.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /upload/process: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Startup ---
@app.on_event("startup")
def startup_event():
    session_manager.start_cleanup_scheduler(
        timeout_seconds=int(DEFAULT_TIMEOUT_SECONDS)
    )
    logger.info("AutoVoyce API started")


@app.on_event("shutdown")
def shutdown_event():
    """Gracefully shut down the background executor."""
    logger.info("Shutting down background executor...")
    _background_executor.shutdown(wait=False)
    logger.info("AutoVoyce API stopped")


# --- SSE Stream ---
# The stream ends after one of these, so clients don't hold connections forever
TERMINAL_EVENT_TYPES = {"processing_complete", "processing_error"}
SSE_KEEPALIVE_SECONDS = 15.0
# Headers that stop proxies from buffering server-sent events
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "X-Content-Type-Options": "nosniff",
    "Content-Type": "text/event-stream; charset=utf-8",
}

@app.get("/upload/status/{session_id}")
async def stream_processing_status(session_id: str):
    """
    Server-Sent Events endpoint for streaming processing status updates.
    Frontend connects to this endpoint to receive real-time updates.
    """
    async def event_generator():
        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue = asyncio.Queue()

        def on_event(event):
            # Called from worker threads: hand the event to the event loop safely
            try:
                loop.call_soon_threadsafe(event_queue.put_nowait, event)
            except RuntimeError:
                pass  # loop already closed (client gone / shutdown)

        # Subscribe and read history in one step so no event is lost or duplicated
        history = event_emitter.subscribe_with_history(session_id, on_event)

        try:
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to processing status stream'})}\n\n"

            for event in history:
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in TERMINAL_EVENT_TYPES:
                    return

            while True:
                try:
                    event = await asyncio.wait_for(
                        event_queue.get(), timeout=SSE_KEEPALIVE_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in TERMINAL_EVENT_TYPES:
                    return
        finally:
            event_emitter.unsubscribe(session_id, on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


# --- Query ---
def _resolve_session(request: QueryRequest, x_session_id: Optional[str]) -> tuple[str, str]:
    """Return (session_id, namespace) or raise 401/404."""
    session_id = x_session_id or request.session_id
    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="No active session. Please provide session_id or upload data first.",
        )
    session_manager.update_last_access(session_id)
    namespace = session_manager.get_namespace(session_id)
    if not namespace:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    _ensure_processed(session_id)
    return session_id, namespace


_PROCESSING_EVENTS = {"processing_started", "processing_complete", "processing_error"}


def _ensure_processed(session_id: str) -> None:
    """Raise 409 unless the session's videos have finished processing."""
    last = next(
        (e["type"] for e in reversed(event_emitter.get_events(session_id))
         if e["type"] in _PROCESSING_EVENTS),
        None,
    )
    if last is None:
        raise HTTPException(
            status_code=409,
            detail="No videos have been processed yet. Select videos on the Ingestion page and process them first.",
        )
    if last == "processing_started":
        raise HTTPException(
            status_code=409,
            detail="Your videos are still being processed. Please ask again once processing is complete.",
        )


@app.post("/query")
async def query_endpoint(
    request: QueryRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """Answer a question about the session's videos (not streamed)."""
    session_id, namespace = _resolve_session(request, x_session_id)
    logger.info(f"Query for session {session_id} (namespace {namespace})")
    try:
        result = await answer(
            session_id, namespace, request.user_query, executor=_background_executor
        )
    except AnswerError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"response": result["response"], "namespace": namespace, "sources": result["sources"]}


@app.post("/query/stream")
async def query_stream_endpoint(
    request: QueryRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Answer a question as server-sent events: "sources", then "token"s, then
    "done" (or one "error"). Session problems return normal 4xx JSON.
    """
    session_id, namespace = _resolve_session(request, x_session_id)
    logger.info(f"Streaming query for session {session_id} (namespace {namespace})")

    async def event_generator():
        async for event in stream_answer(
            session_id, namespace, request.user_query, executor=_background_executor
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream", headers=SSE_HEADERS
    )


# --- TTS ---
@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech using Microsoft Edge TTS (free, no API key needed).
    Returns audio as MP3 using in-memory buffer (no temp files).
    """
    import edge_tts
    import io

    try:
        text = request.text
        voice_mapping = {
            "21m00Tcm4TlvDq8ikWAM": "en-US-AriaNeural",
            "EXAVITQu4vr4xnSDxMaL": "en-US-GuyNeural",
            "en-US-Neural2-F": "en-US-AriaNeural",
            "en-US-Neural2-D": "en-US-GuyNeural",
        }
        voice = voice_mapping.get(request.voice_id, "en-US-AriaNeural")

        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        text = _trim_for_tts(text)

        logger.info(f"TTS request: voice={voice}, text_length={len(text)}")

        # Stream audio into memory buffer (no temp files)
        communicate = edge_tts.Communicate(text, voice)
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_content = audio_buffer.getvalue()
        audio_buffer.close()

        logger.info(f"TTS complete: {len(audio_content)} bytes")

        from fastapi.responses import Response as FastAPIResponse
        return FastAPIResponse(
            content=audio_content,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

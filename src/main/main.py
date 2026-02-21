from fastapi import FastAPI, HTTPException, Response, Cookie, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from src.workflow.workflow import processing_workflow
from src.agents.pinecone_query_agent import query_agent
from src.agents.youtube_retriever_agent import retriever_agent_with_metadata
from src.utils import session_manager
from src.utils.event_emitter import event_emitter
from settings import DEFAULT_TIMEOUT_SECONDS
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
class QueryRequest(BaseModel):
    user_query: str
    session_id: Optional[str] = None


class ProcessRequest(BaseModel):
    video_ids: List[str]
    session_id: Optional[str] = None


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb"


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
async def search_videos(request: QueryRequest, response: Response):
    """
    Phase 1: Searches YouTube for videos matching the query.
    Creates a new session and returns video list for user selection.
    """
    try:
        session_id, namespace = session_manager.create_session()

        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=False,
            samesite="none",
            secure=False,
            max_age=86400,
        )
        logger.info(f"Created session {session_id} -> namespace {namespace}")

        # Run blocking search in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        videos = await loop.run_in_executor(
            _background_executor, retriever_agent_with_metadata, request.user_query
        )

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
        from src.tools.transcript_fetcher import get_transcript_from_api

        logger.info(f"Fetching transcript for video: {video_id}")

        # Run blocking transcript fetch in thread pool
        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(
            _background_executor, get_transcript_from_api, video_id
        )

        if not transcript or transcript.strip() == "":
            raise HTTPException(status_code=404, detail="No transcript available for this video")

        logger.info(f"Got transcript for {video_id}: {len(transcript)} chars")
        return {
            "transcript": transcript,
            "video_id": video_id,
            "segments": len(transcript.split(". ")),
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
    response: Response,
    cookie_session_id: Optional[str] = Cookie(None, alias="session_id"),
):
    """
    Phase 2: Processes selected videos (transcript extraction + Pinecone upload).
    Runs in background thread; frontend connects to SSE for progress.
    """
    try:
        session_id = request.session_id or cookie_session_id

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

        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=False,
            samesite="none",
            secure=False,
            max_age=86400,
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

                video_urls = [
                    f"https://www.youtube.com/watch?v={vid}"
                    for vid in request.video_ids
                ]

                initial_state = {
                    "user_query": "",
                    "video_urls": video_urls,
                    "transcript": "",
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
@app.get("/upload/status/{session_id}")
async def stream_processing_status(session_id: str):
    """
    Server-Sent Events endpoint for streaming processing status updates.
    Frontend connects to this endpoint to receive real-time updates.
    """
    import queue

    async def event_generator():
        yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to processing status stream'})}\n\n"

        event_queue = queue.Queue()

        def on_event(event):
            event_queue.put(event)

        event_emitter.subscribe(session_id, on_event)

        try:
            existing_events = event_emitter.get_events(session_id)
            for event in existing_events:
                yield f"data: {json.dumps(event)}\n\n"

            while True:
                try:
                    event = event_queue.get(timeout=1.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield f": keepalive\n\n"
                    await asyncio.sleep(0.1)
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            event_emitter.unsubscribe(session_id, on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


# --- Query ---
@app.post("/query")
async def query_endpoint(
    request: QueryRequest,
    cookie_session_id: Optional[str] = Cookie(None, alias="session_id"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Invokes the Pinecone Query Agent to answer questions.
    Now async — runs blocking LangChain call in thread pool.
    """
    try:
        session_id = x_session_id or request.session_id or cookie_session_id

        logger.info(f"Query request - session: {session_id}")

        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="No active session. Please provide session_id or upload data first.",
            )

        session_manager.update_last_access(session_id)
        namespace = session_manager.get_namespace(session_id)

        if not namespace:
            raise HTTPException(status_code=404, detail="Session not found or expired.")

        session_manager.set_current_namespace(namespace)
        logger.info(f"Querying namespace {namespace} for session {session_id}")

        # Run blocking LangChain/Gemini call in thread pool — keeps event loop free
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _background_executor, query_agent, request.user_query, namespace, session_id
        )

        return {"response": result, "namespace": namespace}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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

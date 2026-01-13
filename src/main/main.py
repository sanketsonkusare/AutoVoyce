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
import asyncio
import json

app = FastAPI()

# Add CORS middleware
# Get allowed origins from environment variable or use defaults for local development
# Note: Cannot use "*" with credentials=True, must specify explicit origins
ALLOWED_ORIGINS_DEFAULT = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"
ALLOWED_ORIGINS = getenv("ALLOWED_ORIGINS", ALLOWED_ORIGINS_DEFAULT).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Frontend URLs (comma-separated)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


class QueryRequest(BaseModel):
    user_query: str
    session_id: Optional[str] = None  # Allow session_id in request body


class ProcessRequest(BaseModel):
    video_ids: List[str]
    session_id: Optional[str] = None  # Allow session_id in request body


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb"  # Default: Allison


@app.get("/")
def read_root():
    return {"message": "AutoVoyce API is running"}


@app.post("/upload")
async def search_videos(request: QueryRequest, response: Response):
    """
    Phase 1: Searches YouTube for videos matching the query.
    Creates a new session and returns video list for user selection.
    """
    try:
        # Create new session
        session_id, namespace = session_manager.create_session()

        # Set session cookie
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=False,  # Allow JavaScript access for debugging
            samesite="none",  # Required for cross-origin cookies
            secure=False,  # Set to True in production with HTTPS
            max_age=86400,  # 24 hours
        )
        print(f"✅ Set cookie for session: {session_id} with namespace: {namespace}")
        print(
            f"📋 Created session, all sessions now: {session_manager.get_all_sessions()}"
        )

        # Search for videos with metadata
        videos = retriever_agent_with_metadata(request.user_query)

        # Verify session still exists after search
        namespace_check = session_manager.get_namespace(session_id)
        if not namespace_check:
            print(f"⚠️ WARNING: Session {session_id} was lost after search!")
        else:
            print(f"✅ Session {session_id} still exists after search")

        # Return video list for user selection
        response_data = {
            "session_id": session_id,
            "namespace": namespace,
            "status": "search_complete",
            "videos": videos,
            "message": f"Found {len(videos)} videos. Please select which ones to process.",
        }

        print(
            f"Returning video list for session: {session_id}, found {len(videos)} videos"
        )
        return response_data
    except Exception as e:
        print(f"Error in upload endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/process")
async def process_selected_videos(
    request: ProcessRequest,
    response: Response,
    cookie_session_id: Optional[str] = Cookie(None, alias="session_id"),
):
    """
    Phase 2: Processes selected videos (transcript extraction and Pinecone upload).
    Takes selected video_ids and processes them in background.
    """
    try:
        # Get session_id from request body or cookie
        session_id = request.session_id or cookie_session_id

        print(
            f"📥 Process request - Body session_id: {request.session_id}, Cookie session_id: {cookie_session_id}"
        )
        print(f"📋 All active sessions: {session_manager.get_all_sessions()}")

        if not session_id:
            print("❌ No session_id found in request body or cookie")
            raise HTTPException(
                status_code=401,
                detail="No active session. Please search for videos first.",
            )

        # Keep session alive
        session_manager.update_last_access(session_id)

        namespace = session_manager.get_namespace(session_id)
        print(f"🔍 Looked up namespace for session {session_id}: {namespace}")

        if not namespace:
            print(f"❌ Session {session_id} not found in active sessions")
            print(
                f"📋 Available sessions: {list(session_manager.get_all_sessions().keys())}"
            )
            raise HTTPException(
                status_code=404,
                detail="Session not found or expired. Please search for videos again.",
            )

        if not request.video_ids:
            raise HTTPException(
                status_code=400,
                detail="No video IDs provided. Please select at least one video.",
            )

        # Set session cookie if not already set
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=False,
            samesite="none",
            secure=False,
            max_age=86400,
        )

        # Start processing workflow in background
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def run_processing_workflow():
            import sys

            print(f"🔄 BACKGROUND THREAD STARTED for session: {session_id}", flush=True)
            event_emitter.emit(
                session_id,
                "processing_started",
                f"Processing started for {len(request.video_ids)} videos",
            )
            sys.stdout.flush()

            try:
                # Ensure environment variables are loaded in background thread
                from dotenv import load_dotenv

                load_dotenv(".env")
                print(f"✅ Environment loaded", flush=True)

                # Convert video IDs to video URLs
                video_urls = [
                    f"https://www.youtube.com/watch?v={video_id}"
                    for video_id in request.video_ids
                ]

                initial_state = {
                    "user_query": "",  # Not needed for processing
                    "video_urls": video_urls,
                    "transcript": "",
                    "namespace": namespace,
                    "session_id": session_id,  # Pass session_id to workflow for event emission
                }
                print(
                    f"🚀 Starting processing workflow for session: {session_id} with {len(request.video_ids)} videos",
                    flush=True,
                )
                print(f"📋 Video URLs: {video_urls}", flush=True)

                # Update last access at start of processing to prevent cleanup
                session_manager.update_last_access(session_id)
                print(f"✅ Session access updated", flush=True)

                result = processing_workflow.invoke(initial_state)
                print(
                    f"✅ Processing workflow completed for session: {session_id}",
                    flush=True,
                )
                event_emitter.emit(
                    session_id,
                    "processing_complete",
                    "All videos processed successfully",
                )

                # Update last access after processing completes to keep session alive
                session_manager.update_last_access(session_id)
                print(f"✅ Updated last access for session: {session_id}", flush=True)

                return result
            except Exception as e:
                print(f"❌ Error in processing workflow: {str(e)}", flush=True)
                import traceback

                traceback.print_exc()
                sys.stdout.flush()
                raise

        # Run in background thread (fire and forget)
        print(f"📤 Scheduling background processing for session: {session_id}")
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        future = loop.run_in_executor(executor, run_processing_workflow)

        # Add error callback to catch any issues
        def handle_future_result(fut):
            try:
                fut.result()  # This will raise if there was an error
            except Exception as e:
                print(f"❌ Background processing failed: {e}", flush=True)
                import traceback

                traceback.print_exc()

        future.add_done_callback(handle_future_result)
        print(f"✅ Background task scheduled", flush=True)

        # Return immediately
        response_data = {
            "session_id": session_id,
            "namespace": namespace,
            "status": "processing",
            "video_count": len(request.video_ids),
            "message": f"Processing {len(request.video_ids)} selected videos. You can start querying in a few moments.",
        }

        print(f"Returning immediate response for processing session: {session_id}")
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in process endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
def startup_event():
    # Start the background cleanup scheduler (checks every 60s, expires after DEFAULT_TIMEOUT_SECONDS)
    session_manager.start_cleanup_scheduler(
        timeout_seconds=int(DEFAULT_TIMEOUT_SECONDS)
    )


@app.get("/upload/status/{session_id}")
async def stream_processing_status(session_id: str):
    """
    Server-Sent Events endpoint for streaming processing status updates.
    Frontend connects to this endpoint to receive real-time updates.
    """
    import queue
    import threading

    async def event_generator():
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to processing status stream'})}\n\n"

        # Thread-safe queue for events
        event_queue = queue.Queue()

        def on_event(event):
            """Callback to add events to the queue (called from background thread)"""
            event_queue.put(event)

        # Subscribe to events for this session
        event_emitter.subscribe(session_id, on_event)

        try:
            # Send any existing events first
            existing_events = event_emitter.get_events(session_id)
            for event in existing_events:
                yield f"data: {json.dumps(event)}\n\n"

            # Keep connection alive and stream new events
            while True:
                try:
                    # Wait for new event with timeout (non-blocking check)
                    try:
                        event = event_queue.get(timeout=1.0)
                        yield f"data: {json.dumps(event)}\n\n"
                    except queue.Empty:
                        # Send keepalive
                        yield f": keepalive\n\n"
                        await asyncio.sleep(0.1)  # Small delay to prevent busy loop
                        continue
                except Exception as e:
                    print(f"Error in SSE stream: {e}", flush=True)
                    break
        except asyncio.CancelledError:
            pass
        finally:
            # Unsubscribe when client disconnects
            event_emitter.unsubscribe(session_id, on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        },
    )


@app.post("/query")
def query_endpoint(
    request: QueryRequest,
    cookie_session_id: Optional[str] = Cookie(None, alias="session_id"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Invokes the Pinecone Query Agent to answer questions based on the knowledge base.
    Uses session_id from header, request body, or cookie to determine which namespace to query.
    """
    try:
        # Get session_id from header, request body, or cookie (in that priority order)
        session_id = x_session_id or request.session_id or cookie_session_id

        print(
            f"📥 Received query request. Header session_id: {x_session_id}, Body session_id: {request.session_id}, Cookie session_id: {cookie_session_id}"
        )
        print(f"📋 Active sessions: {session_manager.get_all_sessions()}")

        if not session_id:
            print("❌ No session_id found in request body or cookie")
            raise HTTPException(
                status_code=401,
                detail="No active session. Please provide session_id or upload data first.",
            )

        # Keep session alive
        session_manager.update_last_access(session_id)

        namespace = session_manager.get_namespace(session_id)
        print(f"🔍 Looked up namespace for session {session_id}: {namespace}")

        if not namespace:
            print(f"❌ Session {session_id} not found in active sessions")
            raise HTTPException(status_code=404, detail="Session not found or expired.")

        # Set namespace in context for query_tool to access
        session_manager.set_current_namespace(namespace)
        print(f"✅ Set namespace in context: {namespace}")

        # Query with session-specific namespace
        result = query_agent(request.user_query, namespace=namespace)
        return {"response": result, "namespace": namespace}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scribe-token")
async def get_scribe_token():
    """
    This endpoint was used for ElevenLabs Realtime Speech-to-Text.
    Since we've switched to Edge TTS, this endpoint is deprecated.
    The frontend should use Web Speech API for speech-to-text instead.
    """
    print("⚠️ /scribe-token endpoint called - This is deprecated (ElevenLabs removed)")
    raise HTTPException(
        status_code=501,
        detail="ElevenLabs integration has been removed. Use Web Speech API for speech-to-text.",
    )


@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech using Microsoft Edge TTS (free, no API key needed).
    Returns audio as MP3.
    """
    import edge_tts
    import tempfile
    import os
    
    print(f"🔊 TTS request received")
    
    try:
        text = request.text
        # Map common voice IDs to Edge TTS voices, or use default
        voice_mapping = {
            "21m00Tcm4TlvDq8ikWAM": "en-US-AriaNeural",  # Default female
            "EXAVITQu4vr4xnSDxMaL": "en-US-GuyNeural",   # Male voice
            "en-US-Neural2-F": "en-US-AriaNeural",
            "en-US-Neural2-D": "en-US-GuyNeural",
        }
        voice = voice_mapping.get(request.voice_id, "en-US-AriaNeural")
        
        print(f"🔊 Processing TTS: voice={voice}, text_length={len(text) if text else 0}")

        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Generate speech using Edge TTS
        print(f"🎤 Generating speech with Edge TTS...")
        communicate = edge_tts.Communicate(text, voice)
        
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_path = tmp_file.name
        
        await communicate.save(tmp_path)
        
        # Read the audio file
        with open(tmp_path, "rb") as audio_file:
            audio_content = audio_file.read()
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        print(f"✅ TTS completed, audio size: {len(audio_content)} bytes")
        
        # Return audio as MP3
        from fastapi.responses import Response as FastAPIResponse
        return FastAPIResponse(
            content=audio_content,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=speech.mp3",
            },
        )
        
    except Exception as e:
        print(f"❌ TTS Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

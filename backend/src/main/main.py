from fastapi import FastAPI, HTTPException, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from src.workflow.workflow import workflow
from src.agents.pinecone_query_agent import query_agent
from src.utils import session_manager
from settings import DEFAULT_TIMEOUT_SECONDS

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


class QueryRequest(BaseModel):
    user_query: str
    session_id: Optional[str] = None  # Allow session_id in request body


@app.get("/")
def read_root():
    return {"message": "AutoVoyce API is running"}


@app.post("/upload")
async def run_workflow(request: QueryRequest, response: Response):
    """
    Invokes the main AutoVoyce workflow with the provided user request.
    Creates a new session and sets a session cookie.
    Returns immediately while processing continues in background.
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
            max_age=86400  # 24 hours
        )
        print(f"✅ Set cookie for session: {session_id} with namespace: {namespace}")
        
        # Start workflow in background
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        def run_workflow_sync():
            initial_state = {
                "user_query": request.user_query,
                "video_ids": [],
                "transcript": "",
                "namespace": namespace
            }
            print(f"Starting workflow for session: {session_id}")
            result = workflow.invoke(initial_state)
            print(f"Workflow completed for session: {session_id}")
            return result
        
        # Run in background thread (fire and forget)
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        loop.run_in_executor(executor, run_workflow_sync)
        
        # Return immediately
        response_data = {
            "session_id": session_id,
            "namespace": namespace,
            "status": "processing",
            "message": "Upload started. You can start querying in a few moments."
        }
        
        print(f"Returning immediate response for session: {session_id}")
        return response_data
    except Exception as e:
        print(f"Error in upload endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
def startup_event():
    # Start the background cleanup scheduler (checks every 60s, expires after DEFAULT_TIMEOUT_SECONDS)
    session_manager.start_cleanup_scheduler(timeout_seconds=int(DEFAULT_TIMEOUT_SECONDS))

@app.post("/query")
def query_endpoint(request: QueryRequest, cookie_session_id: Optional[str] = Cookie(None, alias="session_id")):
    """
    Invokes the Pinecone Query Agent to answer questions based on the knowledge base.
    Uses session_id from request body or cookie to determine which namespace to query.
    """
    try:
        # Get session_id from request body or cookie
        session_id = request.session_id or cookie_session_id
        
        print(f"📥 Received query request. Body session_id: {request.session_id}, Cookie session_id: {cookie_session_id}")
        print(f"📋 Active sessions: {session_manager.get_all_sessions()}")
        
        if not session_id:
            print("❌ No session_id found in request body or cookie")
            raise HTTPException(status_code=401, detail="No active session. Please provide session_id or upload data first.")
        
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





if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

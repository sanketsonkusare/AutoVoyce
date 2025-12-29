import time
import uuid
import threading
from typing import Dict, Optional
from pinecone import Pinecone
from settings import PINECONE_API_KEY, PINECONE_HOST_URL, DEFAULT_TIMEOUT_SECONDS

# In-memory session store (session_id -> namespace)
_sessions: Dict[str, str] = {}
_session_last_access: Dict[str, float] = {}  # session_id -> timestamp
_last_session_id: Optional[str] = None
_scheduler_thread: Optional[threading.Thread] = None
_stop_scheduler: threading.Event = threading.Event()

# Thread-local storage for current namespace context
_context = threading.local()

def create_session() -> tuple[str, str]:
    """
    Creates a new session with a unique ID and Pinecone namespace.
    Returns: (session_id, namespace)
    """
    global _last_session_id
    session_id = str(uuid.uuid4())
    namespace = f"session_{session_id[:8]}"  # Use first 8 chars for readability
    _sessions[session_id] = namespace
    _session_last_access[session_id] = time.time()
    _last_session_id = session_id
    print(f"✅ Created session: {session_id} -> {namespace}")
    print(f"📋 Total sessions now: {len(_sessions)}")
    print(f"📋 Session keys: {list(_sessions.keys())}")
    return session_id, namespace

def update_last_access(session_id: str):
    """Updates the last access timestamp for a session."""
    if session_id in _sessions:
        _session_last_access[session_id] = time.time()

def get_last_session_id() -> Optional[str]:
    """Returns the most recently created session ID."""
    return _last_session_id

def get_namespace(session_id: str) -> Optional[str]:
    """
    Retrieves the namespace for a given session ID.
    Returns: namespace or None if session doesn't exist
    """
    namespace = _sessions.get(session_id)
    if not namespace:
        print(f"⚠️ Session {session_id} not found in _sessions dict")
        print(f"📋 Current sessions: {list(_sessions.keys())}")
    return namespace

def set_current_namespace(namespace: str):
    """
    Sets the current namespace in thread-local context.
    This allows tools to access the namespace without explicit parameter passing.
    """
    _context.namespace = namespace

def get_current_namespace() -> Optional[str]:
    """
    Gets the current namespace from thread-local context.
    Returns: namespace or None if not set
    """
    return getattr(_context, 'namespace', None)

def delete_session(session_id: str) -> bool:
    """
    Deletes a session and its associated Pinecone namespace.
    Returns: True if session was deleted, False if it didn't exist
    """
    print(f"🗑️ Attempting to delete session: {session_id}")
    print(f"📋 Sessions before delete: {list(_sessions.keys())}")
    namespace = _sessions.pop(session_id, None)
    _session_last_access.pop(session_id, None)
    print(f"📋 Sessions after delete: {list(_sessions.keys())}")
    
    if namespace:
        print(f"📦 Found namespace to delete: {namespace}")
        try:
            # Delete all vectors in the namespace
            pc = Pinecone(api_key=PINECONE_API_KEY)
            index = pc.Index(host=PINECONE_HOST_URL)
            
            print(f"🔄 Calling index.delete_namespace(namespace='{namespace}')...")
            index.delete_namespace(namespace=namespace)
            
            print(f"✅ Successfully deleted Pinecone namespace: {namespace}")
            return True
        except Exception as e:
            print(f"❌ Error deleting namespace {namespace}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print(f"⚠️ No namespace found for session {session_id}")
        return False
    return False

def cleanup_expired_sessions(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
    """
    Checks for and deletes sessions that haven't been accessed in timeout_seconds.
    """
    current_time = time.time()
    expired_sessions = []
    
    # Identify expired sessions
    for session_id, last_access in list(_session_last_access.items()):
        if current_time - last_access > timeout_seconds:
            expired_sessions.append(session_id)
            
    # Delete them
    for session_id in expired_sessions:
        print(f"⏰ Session {session_id} expired (inactive > {timeout_seconds}s). Cleaning up...")
        delete_session(session_id)

def start_cleanup_scheduler(interval_seconds: int = 300, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
    """
    Starts a background thread that runs cleanup every interval_seconds.
    Default interval is 5 minutes (300s) to check for expired sessions.
    """
    global _scheduler_thread, _stop_scheduler
    
    if _scheduler_thread and _scheduler_thread.is_alive():
        return  # Already running
        
    _stop_scheduler.clear()
    
    def scheduler_loop():
        timeout_hours = timeout_seconds / 3600
        print(f"🕒 Session cleanup scheduler started (Check every {interval_seconds}s, Expire after {timeout_hours:.1f} hours)")
        while not _stop_scheduler.is_set():
            try:
                cleanup_expired_sessions(timeout_seconds)
                # stored wait to allow clean exit
                for _ in range(interval_seconds):
                    if _stop_scheduler.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                print(f"❌ Error in cleanup scheduler: {e}")
                time.sleep(60) # Wait a bit before retrying on error
                
    _scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    _scheduler_thread.start()

def get_all_sessions() -> Dict[str, str]:
    """Returns all active sessions (for debugging)"""
    return _sessions.copy()

import time
import uuid
import threading
import logging
from typing import Dict, Optional
from pinecone import Pinecone
from settings import PINECONE_API_KEY, PINECONE_HOST_URL, DEFAULT_TIMEOUT_SECONDS

logger = logging.getLogger("autovoyce.sessions")

# Thread-safe session store
_lock = threading.Lock()
_sessions: Dict[str, str] = {}
_session_last_access: Dict[str, float] = {}
_last_session_id: Optional[str] = None
_scheduler_thread: Optional[threading.Thread] = None
_stop_scheduler: threading.Event = threading.Event()

# Thread-local storage for current namespace context
_context = threading.local()


def _check_pinecone_namespace_limit(max_namespaces: int = 90):
    """
    Guard against hitting Pinecone's 100-namespace limit.
    If we're at max_namespaces or above, purge the oldest session_ namespaces.
    This handles orphaned namespaces from server restarts.
    """
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(host=PINECONE_HOST_URL)
        stats = index.describe_index_stats()
        namespaces = stats.get("namespaces", {})
        session_namespaces = [ns for ns in namespaces if ns.startswith("session_")]

        if len(session_namespaces) >= max_namespaces:
            # Delete the half with fewest vectors (likely stale/test sessions)
            ns_by_vectors = sorted(
                session_namespaces,
                key=lambda ns: namespaces[ns].get("vector_count", 0)
            )
            to_delete = ns_by_vectors[:len(ns_by_vectors) // 2]
            logger.warning(
                f"Pinecone namespace limit approaching ({len(session_namespaces)}/100). "
                f"Auto-purging {len(to_delete)} stale namespaces."
            )
            for ns in to_delete:
                try:
                    index.delete(delete_all=True, namespace=ns)
                    logger.info(f"Auto-purged namespace: {ns}")
                except Exception as e:
                    logger.error(f"Failed to purge {ns}: {e}")
    except Exception as e:
        logger.error(f"Namespace limit check failed: {e}")


def create_session() -> tuple[str, str]:
    """
    Creates a new session with a unique ID and Pinecone namespace.
    Thread-safe. Auto-purges stale namespaces if approaching Pinecone limit.
    Returns: (session_id, namespace)
    """
    global _last_session_id

    # Guard against hitting the 100-namespace limit
    _check_pinecone_namespace_limit()

    session_id = str(uuid.uuid4())
    namespace = f"session_{session_id[:8]}"
    with _lock:
        _sessions[session_id] = namespace
        _session_last_access[session_id] = time.time()
        _last_session_id = session_id
        total = len(_sessions)
    logger.info(f"Created session {session_id} -> {namespace} (total: {total})")
    return session_id, namespace


def update_last_access(session_id: str):
    """Updates the last access timestamp for a session. Thread-safe."""
    with _lock:
        if session_id in _sessions:
            _session_last_access[session_id] = time.time()


def get_last_session_id() -> Optional[str]:
    """Returns the most recently created session ID."""
    with _lock:
        return _last_session_id


def get_namespace(session_id: str) -> Optional[str]:
    """
    Retrieves the namespace for a given session ID. Thread-safe.
    Returns: namespace or None if session doesn't exist
    """
    with _lock:
        namespace = _sessions.get(session_id)
    if not namespace:
        logger.warning(f"Session {session_id} not found")
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
    Deletes a session and its associated Pinecone namespace. Thread-safe.
    Returns: True if session was deleted, False if it didn't exist
    """
    with _lock:
        namespace = _sessions.pop(session_id, None)
        _session_last_access.pop(session_id, None)

    if namespace:
        logger.info(f"Deleting session {session_id} (namespace: {namespace})")
        try:
            pc = Pinecone(api_key=PINECONE_API_KEY)
            index = pc.Index(host=PINECONE_HOST_URL)
            index.delete_namespace(namespace=namespace)
            logger.info(f"Deleted Pinecone namespace: {namespace}")
            return True
        except Exception as e:
            logger.error(f"Error deleting namespace {namespace}: {e}", exc_info=True)
            return False
    else:
        logger.warning(f"No namespace found for session {session_id}")
        return False


def cleanup_expired_sessions(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
    """
    Checks for and deletes sessions that haven't been accessed within timeout.
    """
    current_time = time.time()
    with _lock:
        expired_sessions = [
            sid for sid, last_access in _session_last_access.items()
            if current_time - last_access > timeout_seconds
        ]

    for session_id in expired_sessions:
        logger.info(f"Session {session_id} expired (inactive > {timeout_seconds}s)")
        delete_session(session_id)


def start_cleanup_scheduler(interval_seconds: int = 300, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
    """
    Starts a background thread that runs cleanup every interval_seconds.
    """
    global _scheduler_thread, _stop_scheduler

    if _scheduler_thread and _scheduler_thread.is_alive():
        return

    _stop_scheduler.clear()

    def scheduler_loop():
        timeout_hours = timeout_seconds / 3600
        logger.info(f"Cleanup scheduler started (every {interval_seconds}s, expire after {timeout_hours:.1f}h)")
        while not _stop_scheduler.is_set():
            try:
                cleanup_expired_sessions(timeout_seconds)
                for _ in range(interval_seconds):
                    if _stop_scheduler.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Cleanup scheduler error: {e}")
                time.sleep(60)

    _scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    _scheduler_thread.start()


def get_all_sessions() -> Dict[str, str]:
    """Returns all active sessions. Thread-safe."""
    with _lock:
        return _sessions.copy()

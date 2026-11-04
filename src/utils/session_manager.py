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
_videos: Dict[str, Dict[str, dict]] = {}  # session_id -> video_id -> search result
_scheduler_thread: Optional[threading.Thread] = None
_stop_scheduler: threading.Event = threading.Event()


# Pinecone stats are fetched at most this often (seconds)
NAMESPACE_CHECK_INTERVAL_SECONDS = 60
_last_namespace_check: float = 0.0


def _check_pinecone_namespace_limit(max_namespaces: int = 90):
    """
    Guard against hitting Pinecone's 100-namespace limit.

    When session namespaces reach max_namespaces, delete the orphaned ones:
    namespaces whose session no longer exists in memory (e.g. left behind by a
    server restart or redeploy). Namespaces of live sessions are never touched,
    even if they are still empty because processing just started.

    Runs at most once every NAMESPACE_CHECK_INTERVAL_SECONDS.
    """
    global _last_namespace_check

    now = time.time()
    with _lock:
        if now - _last_namespace_check < NAMESPACE_CHECK_INTERVAL_SECONDS:
            return
        _last_namespace_check = now
        live_namespaces = set(_sessions.values())

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(host=PINECONE_HOST_URL)
        stats = index.describe_index_stats()
        namespaces = stats.get("namespaces", {})
        session_namespaces = [ns for ns in namespaces if ns.startswith("session_")]

        if len(session_namespaces) < max_namespaces:
            return

        orphaned = [ns for ns in session_namespaces if ns not in live_namespaces]
        logger.warning(
            f"Pinecone namespace limit approaching ({len(session_namespaces)}/100). "
            f"Purging {len(orphaned)} orphaned namespaces."
        )
        for ns in orphaned:
            try:
                index.delete_namespace(namespace=ns)
                logger.info(f"Purged orphaned namespace: {ns}")
            except Exception as e:
                logger.error(f"Failed to purge {ns}: {e}")

        if len(session_namespaces) - len(orphaned) >= max_namespaces:
            logger.error(
                "Pinecone namespace limit nearly reached by live sessions; "
                "new uploads may fail until sessions expire."
            )
    except Exception as e:
        logger.error(f"Namespace limit check failed: {e}")


def create_session() -> tuple[str, str]:
    """
    Creates a new session with a unique ID and Pinecone namespace.
    Thread-safe. Auto-purges stale namespaces if approaching Pinecone limit.
    Returns: (session_id, namespace)
    """
    # Guard against hitting the 100-namespace limit
    _check_pinecone_namespace_limit()

    session_id = str(uuid.uuid4())
    namespace = f"session_{session_id[:8]}"
    with _lock:
        _sessions[session_id] = namespace
        _session_last_access[session_id] = time.time()
        total = len(_sessions)
    logger.info(f"Created session {session_id} -> {namespace} (total: {total})")
    return session_id, namespace


def update_last_access(session_id: str):
    """Updates the last access timestamp for a session. Thread-safe."""
    with _lock:
        if session_id in _sessions:
            _session_last_access[session_id] = time.time()


def set_videos(session_id: str, videos: list[dict]) -> None:
    """Remember the search results of a session (for titles and channels). Thread-safe."""
    with _lock:
        _videos[session_id] = {video["id"]: video for video in videos if video.get("id")}


def get_video(session_id: str, video_id: str) -> Optional[dict]:
    """Return a video from the session's search results, or None. Thread-safe."""
    with _lock:
        return _videos.get(session_id, {}).get(video_id)


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


def _free_session_memory(session_id: str, namespace: str) -> None:
    """Release everything kept in memory for a session."""
    # Imported here to avoid a circular import at module load time
    from src.utils.event_emitter import event_emitter
    from src.agents.pinecone_query_agent import forget_session

    event_emitter.clear_session(session_id)
    forget_session(namespace, session_id)


def delete_session(session_id: str) -> bool:
    """
    Deletes a session, its in-memory state (events, cached agent, chat
    history) and its Pinecone namespace. Thread-safe.
    Returns: True if the Pinecone namespace was deleted, False otherwise
    """
    with _lock:
        namespace = _sessions.pop(session_id, None)
        _session_last_access.pop(session_id, None)
        _videos.pop(session_id, None)

    if not namespace:
        logger.warning(f"No namespace found for session {session_id}")
        return False

    logger.info(f"Deleting session {session_id} (namespace: {namespace})")
    try:
        _free_session_memory(session_id, namespace)
    except Exception as e:
        logger.error(f"Error freeing memory for session {session_id}: {e}", exc_info=True)

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(host=PINECONE_HOST_URL)
        index.delete_namespace(namespace=namespace)
        logger.info(f"Deleted Pinecone namespace: {namespace}")
        return True
    except Exception as e:
        logger.error(f"Error deleting namespace {namespace}: {e}", exc_info=True)
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

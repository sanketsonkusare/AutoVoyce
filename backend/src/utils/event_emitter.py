"""
Event emitter for processing status updates.
Allows background threads to emit events that can be streamed via SSE.
"""

import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime


class ProcessingEventEmitter:
    """Thread-safe event emitter for processing status updates."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._events: Dict[str, List[dict]] = {}  # Store events per session
        self._lock = threading.Lock()

    def emit(
        self,
        session_id: str,
        event_type: str,
        message: str,
        data: Optional[dict] = None,
    ):
        """
        Emit an event for a specific session.

        Args:
            session_id: The session ID
            event_type: Type of event (e.g., 'video_processed', 'transcript_processing', 'pinecone_upload', etc.)
            message: Human-readable message
            data: Optional additional data
        """
        event = {
            "type": event_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
        }

        with self._lock:
            if session_id not in self._events:
                self._events[session_id] = []
            self._events[session_id].append(event)

            # Notify listeners
            if session_id in self._listeners:
                for callback in self._listeners[session_id]:
                    try:
                        callback(event)
                    except Exception as e:
                        print(f"Error in event callback: {e}", flush=True)

    def subscribe(self, session_id: str, callback: Callable):
        """Subscribe to events for a session."""
        with self._lock:
            if session_id not in self._listeners:
                self._listeners[session_id] = []
            self._listeners[session_id].append(callback)

    def unsubscribe(self, session_id: str, callback: Callable):
        """Unsubscribe from events for a session."""
        with self._lock:
            if session_id in self._listeners:
                try:
                    self._listeners[session_id].remove(callback)
                except ValueError:
                    pass

    def get_events(self, session_id: str) -> List[dict]:
        """Get all events for a session."""
        with self._lock:
            return self._events.get(session_id, []).copy()

    def clear_events(self, session_id: str):
        """Clear events for a session."""
        with self._lock:
            if session_id in self._events:
                del self._events[session_id]


# Global event emitter instance
event_emitter = ProcessingEventEmitter()

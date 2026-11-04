"""Short per-session chat history (in memory)."""

from collections import deque
import re
import threading

MAX_EXCHANGES = 6

_lock = threading.Lock()
_history: dict[str, deque] = {}

# A bare citation marker like [3] (not a Markdown link like [3](https://...))
_CITATION = re.compile(r"\s*\[\d+\](?!\()")


def strip_citations(text: str) -> str:
    """Remove [n] markers: their numbers only mean something within one answer."""
    text = _CITATION.sub("", text)
    return re.sub(r"[ \t]+([.,;:!?])", r"\1", text).strip()


def add_exchange(session_id: str, question: str, answer: str) -> None:
    with _lock:
        _history.setdefault(session_id, deque(maxlen=MAX_EXCHANGES)).append(
            (question, strip_citations(answer))
        )


def get_history(session_id: str) -> list[tuple[str, str]]:
    with _lock:
        return list(_history.get(session_id, ()))


def clear(session_id: str) -> None:
    with _lock:
        _history.pop(session_id, None)

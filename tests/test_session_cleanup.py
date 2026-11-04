from unittest.mock import MagicMock

import pytest

from src.rag import history
from src.utils import session_manager
from src.utils.event_emitter import event_emitter


@pytest.fixture
def fake_pinecone(monkeypatch):
    index = MagicMock()
    index.describe_index_stats.return_value = {"namespaces": {}}
    pc = MagicMock()
    pc.Index.return_value = index
    monkeypatch.setattr(session_manager, "Pinecone", lambda **_: pc)
    return index


def test_delete_session_frees_all_in_memory_state(fake_pinecone):
    session_id, namespace = session_manager.create_session()

    # Simulate state built up while the session was used
    event_emitter.emit(session_id, "processing_started", "start")
    event_emitter.subscribe_with_history(session_id, lambda e: None)
    history.add_exchange(session_id, "q", "a")

    assert session_manager.delete_session(session_id) is True

    assert session_manager.get_namespace(session_id) is None
    assert session_id not in event_emitter._events
    assert session_id not in event_emitter._listeners
    assert history.get_history(session_id) == []
    fake_pinecone.delete_namespace.assert_called_once_with(namespace=namespace)


def test_delete_session_frees_memory_even_if_pinecone_fails(fake_pinecone):
    session_id, namespace = session_manager.create_session()
    event_emitter.emit(session_id, "processing_started", "start")
    history.add_exchange(session_id, "q", "a")
    fake_pinecone.delete_namespace.side_effect = RuntimeError("pinecone down")

    session_manager.delete_session(session_id)

    assert session_id not in event_emitter._events
    assert history.get_history(session_id) == []

from unittest.mock import MagicMock

import pytest

from src.utils import session_manager


@pytest.fixture
def index(monkeypatch):
    index = MagicMock()
    pc = MagicMock()
    pc.Index.return_value = index
    monkeypatch.setattr(session_manager, "Pinecone", lambda **_: pc)
    monkeypatch.setattr(session_manager, "_last_namespace_check", 0.0)
    return index


def _stats(namespaces: dict[str, int]) -> dict:
    return {"namespaces": {ns: {"vector_count": n} for ns, n in namespaces.items()}}


def test_purge_spares_live_sessions_and_deletes_only_orphans(index, monkeypatch):
    live = {f"live-{i}": f"session_live{i:04d}" for i in range(5)}
    monkeypatch.setattr(session_manager, "_sessions", dict(live))

    namespaces = {ns: 0 for ns in live.values()}           # live, still empty
    orphans = {f"session_orph{i:04d}": 500 for i in range(6)}  # left by a restart
    namespaces.update(orphans)
    namespaces["youtube_transcripts"] = 1000                 # not a session namespace
    index.describe_index_stats.return_value = _stats(namespaces)

    session_manager._check_pinecone_namespace_limit(max_namespaces=10)

    deleted = {c.kwargs["namespace"] for c in index.delete_namespace.call_args_list}
    assert deleted == set(orphans)


def test_no_purge_below_limit(index, monkeypatch):
    monkeypatch.setattr(session_manager, "_sessions", {})
    index.describe_index_stats.return_value = _stats({"session_a": 1, "session_b": 1})

    session_manager._check_pinecone_namespace_limit(max_namespaces=10)

    index.delete_namespace.assert_not_called()


def test_check_is_throttled(index, monkeypatch):
    monkeypatch.setattr(session_manager, "_sessions", {})
    index.describe_index_stats.return_value = _stats({})

    session_manager._check_pinecone_namespace_limit()
    session_manager._check_pinecone_namespace_limit()

    assert index.describe_index_stats.call_count == 1

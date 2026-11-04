from unittest.mock import MagicMock

import httpx
import pytest

from src.main import main as main_module
from src.utils import session_manager

VIDEO = {"id": "abcdefghijk", "title": "T", "channel": "C", "link": "", "thumbnail": "",
         "duration": "1:00", "views": "1"}


@pytest.fixture
def fake_pinecone(monkeypatch):
    index = MagicMock()
    index.describe_index_stats.return_value = {"namespaces": {}}
    pc = MagicMock()
    pc.Index.return_value = index
    monkeypatch.setattr(session_manager, "Pinecone", lambda **_: pc)
    return index


def test_videos_are_stored_and_looked_up(fake_pinecone):
    sid, _ = session_manager.create_session()
    session_manager.set_videos(sid, [VIDEO])
    assert session_manager.get_video(sid, "abcdefghijk")["title"] == "T"
    assert session_manager.get_video(sid, "zzzzzzzzzzz") is None


def test_videos_removed_with_session(fake_pinecone):
    sid, _ = session_manager.create_session()
    session_manager.set_videos(sid, [VIDEO])
    session_manager.delete_session(sid)
    assert session_manager.get_video(sid, "abcdefghijk") is None


async def test_upload_stores_search_results(fake_pinecone, monkeypatch):
    monkeypatch.setattr(main_module, "retriever_agent_with_metadata", lambda q: [VIDEO])
    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/upload", json={"user_query": "phones"})
    sid = resp.json()["session_id"]
    assert session_manager.get_video(sid, "abcdefghijk")["channel"] == "C"

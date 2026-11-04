import json
from unittest.mock import MagicMock

import httpx
import pytest

from src.main import main as main_module
from src.rag import answer as answer_module
from src.rag import history
from src.utils import session_manager
from tests.fakes import FakeChatModel


def _parse(body: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in body.splitlines() if line.startswith("data: ")]


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=main_module.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def live_session(monkeypatch, fake_index):
    index = MagicMock()
    index.describe_index_stats.return_value = {"namespaces": {}}
    pc = MagicMock()
    pc.Index.return_value = index
    monkeypatch.setattr(session_manager, "Pinecone", lambda **_: pc)
    sid, namespace = session_manager.create_session()
    fake_index.records[namespace] = [{
        "_id": "abcdefghijk-0", "chunk_text": "battery lasts all day", "video_id": "abcdefghijk",
        "title": "Phone Review", "channel": "Tech", "start_seconds": 272}]
    model = FakeChatModel(chunks=["Battery is ", "great [1]."], calls=[])
    monkeypatch.setattr(answer_module, "get_model", lambda: model)
    yield sid
    history.clear(sid)


async def test_stream_events_and_headers(client, live_session):
    async with client:
        resp = await client.post("/query/stream", json={"user_query": "battery?"},
                                 headers={"X-Session-ID": live_session})
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse(resp.text)
    assert [e["type"] for e in events] == ["sources", "token", "token", "done"]
    assert events[0]["sources"][0]["url"] == "https://www.youtube.com/watch?v=abcdefghijk&t=272s"
    assert events[-1]["answer"] == "Battery is great [1]."


async def test_stream_unknown_session_is_404_json(client):
    async with client:
        resp = await client.post("/query/stream", json={"user_query": "hi", "session_id": "nope"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Session not found or expired."


async def test_stream_missing_session_is_401(client):
    async with client:
        resp = await client.post("/query/stream", json={"user_query": "hi"})
    assert resp.status_code == 401


async def test_stream_validation_is_422(client):
    async with client:
        resp = await client.post("/query/stream", json={"user_query": "", "session_id": "x"})
    assert resp.status_code == 422


async def test_stream_error_event(client, live_session, fake_index):
    fake_index.fail_search = True
    async with client:
        resp = await client.post("/query/stream", json={"user_query": "q", "session_id": live_session})
    assert _parse(resp.text) == [
        {"type": "error", "message": "Couldn't search your videos. Please try again."}]


async def test_query_returns_sources(client, live_session):
    async with client:
        body = (await client.post("/query", json={"user_query": "battery?", "session_id": live_session})).json()
    assert set(body) == {"response", "namespace", "sources"}
    assert body["response"] == "Battery is great [1]." and body["sources"][0]["n"] == 1


async def test_query_answer_error_is_502(client, live_session, fake_index):
    fake_index.fail_search = True
    async with client:
        resp = await client.post("/query", json={"user_query": "q", "session_id": live_session})
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Couldn't search your videos. Please try again."

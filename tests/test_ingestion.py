import asyncio
from unittest.mock import MagicMock

import httpx
import pytest

from src.tools import pinecone_uploader
from src.tools.pinecone_uploader import build_records, upload_transcripts
from src.utils import session_manager
from src.utils.event_emitter import event_emitter


def test_build_records_fields_and_ids():
    t = {"video_id": "abcdefghijk", "title": "T", "channel": "C",
         "segments": [{"text": "a" * 600, "start": 12.7}, {"text": "b" * 600, "start": 40.0}]}
    recs = build_records(t)
    assert [r["_id"] for r in recs] == ["abcdefghijk-0", "abcdefghijk-1"]
    assert recs[0] | {"chunk_text": None} == {
        "_id": "abcdefghijk-0", "chunk_text": None, "video_id": "abcdefghijk",
        "title": "T", "channel": "C", "start_seconds": 12}
    assert recs[1]["chunk_text"] == "b" * 600 and recs[1]["start_seconds"] == 40


def test_unknown_start_is_minus_one():
    t = {"video_id": "abcdefghijk", "title": "T", "channel": "C",
         "segments": [{"text": "x", "start": None}]}
    assert build_records(t)[0]["start_seconds"] == -1


def test_upload_batches_of_96(fake_index):
    t = {"video_id": "abcdefghijk", "title": "T", "channel": "C",
         "segments": [{"text": "w" * 990, "start": float(i)} for i in range(200)]}
    assert upload_transcripts([t], "ns") == 200
    assert [c["count"] for c in fake_index.upsert_calls] == [96, 96, 8]


def test_reprocessing_overwrites_instead_of_duplicating(fake_index):
    t = {"video_id": "abcdefghijk", "title": "T", "channel": "C",
         "segments": [{"text": "hello", "start": 1.0}]}
    upload_transcripts([t], "ns")
    upload_transcripts([t], "ns")
    assert len(fake_index.records["ns"]) == 1


def _fake_transcripts(monkeypatch):
    from src.agents import youtube_transcript_agent as agent

    def fetch(video_id):
        if video_id == "ccccccccccc":
            raise Exception("No captions available: none")
        return [{"text": f"talk about {video_id}", "start": 5.0}]

    monkeypatch.setattr(agent, "get_transcript_from_api", fetch)


def test_workflow_uploads_each_video_with_titles(fake_index, monkeypatch):
    from src.workflow.workflow import processing_workflow

    _fake_transcripts(monkeypatch)
    event_emitter.clear_session("s-wf")
    processing_workflow.invoke({
        "videos": [{"id": "aaaaaaaaaa1", "title": "T1", "channel": "C1"},
                   {"id": "ccccccccccc", "title": "T3", "channel": "C3"}],
        "namespace": "ns-wf", "session_id": "s-wf",
    })
    recs = fake_index.records["ns-wf"]
    assert {r["video_id"] for r in recs} == {"aaaaaaaaaa1"}
    assert recs[0]["title"] == "T1" and recs[0]["start_seconds"] == 5
    types = [e["type"] for e in event_emitter.get_events("s-wf")]
    assert "video_processed" in types and "video_error" in types
    assert types[-1] == "pinecone_upload_complete"


@pytest.fixture
def session_pinecone(monkeypatch):
    index = MagicMock()
    index.describe_index_stats.return_value = {"namespaces": {}}
    pc = MagicMock()
    pc.Index.return_value = index
    monkeypatch.setattr(session_manager, "Pinecone", lambda **_: pc)


async def test_process_endpoint_uses_session_titles(fake_index, session_pinecone, monkeypatch):
    from src.main import main as main_module

    _fake_transcripts(monkeypatch)
    sid, namespace = session_manager.create_session()
    session_manager.set_videos(sid, [{"id": "aaaaaaaaaa1", "title": "T1", "channel": "C1"}])

    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/upload/process", json={
            "video_ids": ["aaaaaaaaaa1", "bbbbbbbbbb2"], "session_id": sid})
    assert resp.status_code == 200

    for _ in range(100):
        if any(e["type"] in ("processing_complete", "processing_error")
               for e in event_emitter.get_events(sid)):
            break
        await asyncio.sleep(0.05)
    titles = {r["video_id"]: (r["title"], r["channel"]) for r in fake_index.records[namespace]}
    assert titles == {"aaaaaaaaaa1": ("T1", "C1"), "bbbbbbbbbb2": ("YouTube video", "")}

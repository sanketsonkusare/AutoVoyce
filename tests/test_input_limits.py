import httpx
import pytest

from settings import SEARCH_LIMIT
from src.main import main as main_module


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=main_module.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_query_rejects_overlong_text(client):
    async with client:
        resp = await client.post("/query", json={"user_query": "x" * 2001, "session_id": "s"})
    assert resp.status_code == 422


async def test_query_rejects_empty_text(client):
    async with client:
        resp = await client.post("/query", json={"user_query": "", "session_id": "s"})
    assert resp.status_code == 422


async def test_process_rejects_too_many_videos(client):
    ids = [f"abcdefghij{i % 10}" for i in range(SEARCH_LIMIT + 1)]
    async with client:
        resp = await client.post("/upload/process", json={"video_ids": ids, "session_id": "s"})
    assert resp.status_code == 422


async def test_process_rejects_malformed_video_id(client):
    async with client:
        resp = await client.post(
            "/upload/process", json={"video_ids": ["../../etc/passwd"], "session_id": "s"}
        )
    assert resp.status_code == 422


async def test_process_accepts_valid_request_shape(client):
    # Valid shape gets past validation and fails on the unknown session instead
    async with client:
        resp = await client.post(
            "/upload/process", json={"video_ids": ["dQw4w9WgXcQ"], "session_id": "missing"}
        )
    assert resp.status_code == 404


async def test_tts_rejects_huge_payload(client):
    async with client:
        resp = await client.post("/tts", json={"text": "x" * 20001})
    assert resp.status_code == 422


def test_tts_text_is_trimmed_at_sentence_boundary():
    text = ("This is a sentence. " * 400).strip()  # ~8000 chars
    trimmed = main_module._trim_for_tts(text)
    assert len(trimmed) <= main_module.TTS_MAX_SPOKEN_CHARS
    assert trimmed.endswith(".")


def test_tts_short_text_is_unchanged():
    assert main_module._trim_for_tts("Hello there.") == "Hello there."


async def test_validation_errors_have_readable_string_detail(client):
    async with client:
        resp = await client.post("/query", json={"user_query": "x" * 2001, "session_id": "s"})
    detail = resp.json()["detail"]
    assert isinstance(detail, str)
    assert "user_query" in detail

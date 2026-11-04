import json

import httpx
import pytest

import settings
from src.tools import transcript_fetcher as tf
from src.tools.transcript_fetcher import (
    get_transcript_from_api,
    get_transcript_from_captions,
    get_transcript_from_gemini,
    transcript_text,
)

VID = "abcdefghijk"


class _Fetched:
    def __init__(self, raw):
        self._raw = raw

    def to_raw_data(self):
        return self._raw


@pytest.fixture
def fake_ytt(monkeypatch):
    class State:
        raw = [{"text": "hello", "start": 0.0, "duration": 1.0}]
        fail = False

    class FakeApi:
        def __init__(self, *args, **kwargs):
            pass

        def fetch(self, video_id, languages=None):
            if State.fail:
                raise RuntimeError("blocked")
            return _Fetched(State.raw)

        def list(self, video_id):
            raise RuntimeError("blocked")

    monkeypatch.setattr(tf, "YouTubeTranscriptApi", FakeApi)
    monkeypatch.setattr(settings, "TRANSCRIPT_SOURCE", "auto")
    return State


@pytest.fixture
def fake_gemini(monkeypatch):
    import google.genai

    class State:
        text = "full transcript"

    class FakeModels:
        def generate_content(self, **kwargs):
            return type("R", (), {"text": State.text})()

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(google.genai, "Client", FakeClient)
    return State


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIPT_CACHE_DIR", str(tmp_path))
    return tmp_path


def test_captions_become_segments_with_start(fake_ytt):
    fake_ytt.raw = [
        {"text": "hello", "start": 0.0, "duration": 1.5},
        {"text": "  ", "start": 1.5, "duration": 1.0},
        {"text": "world", "start": 2.5, "duration": 1.0},
    ]
    assert get_transcript_from_captions(VID) == [
        {"text": "hello", "start": 0.0},
        {"text": "world", "start": 2.5},
    ]


def test_gemini_returns_single_untimed_segment(fake_gemini):
    fake_gemini.text = "full transcript"
    assert get_transcript_from_gemini(VID) == [{"text": "full transcript", "start": None}]


def test_cache_round_trip_as_json(tmp_cache, fake_ytt):
    first = get_transcript_from_api(VID)
    fake_ytt.fail = True  # second call must come from the cache
    assert get_transcript_from_api(VID) == first
    data = json.loads((tmp_cache / f"{VID}.json").read_text())
    assert data == {"source": "captions", "segments": first}


def test_old_txt_cache_is_ignored(tmp_cache, fake_ytt):
    (tmp_cache / f"{VID}.txt").write_text("stale text")
    assert get_transcript_from_api(VID)[0]["text"] != "stale text"


def test_gemini_fallback_is_cached_with_source(tmp_cache, fake_ytt, fake_gemini):
    fake_ytt.fail = True
    assert get_transcript_from_api(VID) == [{"text": "full transcript", "start": None}]
    data = json.loads((tmp_cache / f"{VID}.json").read_text())
    assert data["source"] == "gemini"


def test_transcript_text_joins_segments():
    assert transcript_text([{"text": "a", "start": 0}, {"text": "b", "start": None}]) == "a b"


async def test_transcript_endpoint_shape(monkeypatch):
    from src.main import main as main_module

    monkeypatch.setattr(
        tf, "get_transcript_from_api",
        lambda vid: [{"text": "a", "start": 0.0}, {"text": "b", "start": 1.0}],
    )
    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/transcript/{VID}")
    assert resp.json() == {"transcript": "a b", "video_id": VID, "segments": 2}

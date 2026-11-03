import asyncio
import json
import threading
import time

import httpx
import pytest

from src.main import main as main_module
from src.utils.event_emitter import event_emitter


def _parse(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=main_module.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_stream_replays_history_once_and_closes_on_complete(client):
    sid = "stream-complete"
    event_emitter.clear_session(sid)
    event_emitter.emit(sid, "processing_started", "start")

    def later():
        time.sleep(0.2)
        event_emitter.emit(sid, "video_processed", "one")
        event_emitter.emit(sid, "processing_complete", "done")

    threading.Thread(target=later).start()
    async with client:
        resp = await asyncio.wait_for(client.get(f"/upload/status/{sid}"), timeout=5)

    types = [e["type"] for e in _parse(resp.text)]
    assert types == ["connected", "processing_started", "video_processed", "processing_complete"]


async def test_stream_closes_immediately_when_already_finished(client):
    sid = "stream-already-done"
    event_emitter.clear_session(sid)
    event_emitter.emit(sid, "processing_error", "boom")

    async with client:
        resp = await asyncio.wait_for(client.get(f"/upload/status/{sid}"), timeout=5)

    assert [e["type"] for e in _parse(resp.text)] == ["connected", "processing_error"]


async def test_open_stream_does_not_block_event_loop(client):
    """While a stream waits for events, other requests must stay fast."""
    sid = "stream-idle"
    event_emitter.clear_session(sid)

    async with client:
        stream_task = asyncio.create_task(client.get(f"/upload/status/{sid}"))
        await asyncio.sleep(0.2)  # let the stream start waiting

        # Measure event-loop responsiveness directly: many short sleeps
        started = time.monotonic()
        for _ in range(20):
            await asyncio.sleep(0.01)
        elapsed = time.monotonic() - started

        health = await client.get("/health")
        event_emitter.emit(sid, "processing_complete", "done")
        await asyncio.wait_for(stream_task, timeout=5)

    assert health.status_code == 200
    # 20 x 10ms sleeps take ~0.2s; a blocked loop would take ~1s per wakeup
    assert elapsed < 0.6

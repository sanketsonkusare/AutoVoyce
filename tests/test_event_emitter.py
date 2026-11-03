from src.utils.event_emitter import ProcessingEventEmitter


def test_subscribe_with_history_returns_past_events_and_gets_new_ones():
    emitter = ProcessingEventEmitter()
    emitter.emit("s1", "processing_started", "start")

    received = []
    history = emitter.subscribe_with_history("s1", received.append)
    emitter.emit("s1", "video_processed", "one")

    assert [e["type"] for e in history] == ["processing_started"]
    assert [e["type"] for e in received] == ["video_processed"]


def test_clear_session_drops_events_and_listeners():
    emitter = ProcessingEventEmitter()
    received = []
    emitter.subscribe_with_history("s1", received.append)
    emitter.emit("s1", "processing_started", "start")

    emitter.clear_session("s1")
    emitter.emit("other", "x", "y")

    assert emitter.get_events("s1") == []
    assert "s1" not in emitter._listeners
    assert "s1" not in emitter._events

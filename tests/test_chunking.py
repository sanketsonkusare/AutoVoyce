from src.tools.chunking import chunk_segments


def seg(text, start):
    return {"text": text, "start": start}


def test_groups_segments_up_to_target_with_one_segment_overlap():
    segs = [seg("a" * 400, 0.0), seg("b" * 400, 10.0), seg("c" * 400, 20.0), seg("d" * 400, 30.0)]
    chunks = chunk_segments(segs, target_chars=1000)
    assert [c["start"] for c in chunks] == [0.0, 10.0, 20.0]
    assert chunks[0]["text"] == "a" * 400 + " " + "b" * 400
    assert chunks[1]["text"].startswith("b" * 400)  # overlap: last segment repeated
    assert all(len(c["text"]) <= 1000 for c in chunks)


def test_oversized_segment_is_its_own_chunk():
    chunks = chunk_segments([seg("x" * 1500, 5.0), seg("y", 9.0)], target_chars=1000)
    assert chunks[0] == {"text": "x" * 1500, "start": 5.0}
    assert chunks[1] == {"text": "y", "start": 9.0}


def test_untimed_text_uses_splitter_and_no_start():
    chunks = chunk_segments([seg("word " * 600, None)])
    assert len(chunks) >= 3 and all(c["start"] is None for c in chunks)
    assert all(len(c["text"]) <= 1000 for c in chunks)


def test_whitespace_is_normalised():  # Review Focus 4
    assert chunk_segments([seg("hello\nworld  again", 1.0)]) == [{"text": "hello world again", "start": 1.0}]


def test_untimed_segment_inside_captions_inherits_chunk_start():
    chunks = chunk_segments([seg("a", 3.0), seg("b", None), seg("c", 7.0)])
    assert chunks == [{"text": "a b c", "start": 3.0}]


def test_empty_input():
    assert chunk_segments([]) == []

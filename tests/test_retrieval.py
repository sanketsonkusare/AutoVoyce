import pytest

from src.rag import retrieval
from src.rag.retrieval import build_search_text, search_passages, video_url


def _record(i, start=10, text="battery life is great"):
    return {"_id": f"abcdefghijk-{i}", "chunk_text": f"{text} {i}", "video_id": "abcdefghijk",
            "title": "Phone Review", "channel": "Tech", "start_seconds": start}


@pytest.fixture
def filled_index(fake_index):
    fake_index.records["ns"] = [_record(i, start=10 * i) for i in range(10)]
    return fake_index


def test_search_text():
    assert build_search_text("what about photos", None) == "what about photos"
    assert build_search_text("what about photos", "best phone?") == "best phone?\nwhat about photos"


def test_video_url():
    assert video_url("abcdefghijk", 272) == "https://www.youtube.com/watch?v=abcdefghijk&t=272s"
    assert video_url("abcdefghijk", None) == "https://www.youtube.com/watch?v=abcdefghijk"


def test_rerank_call_shape(filled_index, monkeypatch):
    monkeypatch.setattr(retrieval, "RERANK_MODEL", "bge-reranker-v2-m3")
    search_passages("ns", "photos?", "best phone?")
    call = filled_index.search_calls[0]
    assert call["query"] == {"inputs": {"text": "best phone?\nphotos?"}, "top_k": 20}
    assert call["rerank"] == {"model": "bge-reranker-v2-m3", "rank_fields": ["chunk_text"],
                              "top_n": 6, "query": "photos?"}
    assert set(call["fields"]) == {"chunk_text", "video_id", "title", "channel", "start_seconds"}


def test_falls_back_without_rerank_on_error(filled_index, monkeypatch):
    monkeypatch.setattr(retrieval, "RERANK_MODEL", "bge-reranker-v2-m3")
    filled_index.fail_rerank = True
    passages = search_passages("ns", "battery")
    assert len(passages) == 6
    assert filled_index.search_calls[-1]["rerank"] is None


def test_rerank_disabled_when_setting_empty(filled_index, monkeypatch):
    monkeypatch.setattr(retrieval, "RERANK_MODEL", "")
    assert len(search_passages("ns", "battery")) == 6
    assert len(filled_index.search_calls) == 1 and filled_index.search_calls[0]["rerank"] is None


def test_passages_numbered_with_urls_and_unknown_time(fake_index):
    fake_index.records["ns"] = [_record(0, start=272), _record(1, start=-1)]
    p = search_passages("ns", "battery")
    assert [x.n for x in p] == [1, 2]
    by_start = {x.start_seconds: x for x in p}
    assert by_start[272].url == "https://www.youtube.com/watch?v=abcdefghijk&t=272s"
    assert by_start[None].url == "https://www.youtube.com/watch?v=abcdefghijk"
    assert p[0].to_dict().keys() == {"n", "video_id", "title", "channel", "start_seconds", "url", "text"}


def test_empty_namespace_returns_no_passages(fake_index):
    assert search_passages("missing", "battery") == []


def test_other_search_errors_propagate(filled_index):
    filled_index.fail_search = True
    with pytest.raises(RuntimeError):
        search_passages("ns", "battery")

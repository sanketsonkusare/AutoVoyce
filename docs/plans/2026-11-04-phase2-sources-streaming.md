# Phase 2: Timestamped Sources, Better Retrieval, Streamed Answers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chat answers cite the videos they come from with `[n]` markers that open YouTube at the exact moment, use better-ranked passages, take one model call, and stream onto the screen.

**Architecture:** Ingestion keeps caption timestamps and stores per-video chunks (with title, channel and start time) in Pinecone. A new `src/rag/` package replaces the LangGraph query agent: search Pinecone (top 20, reranked to 6), number the passages, and make one streamed Gemini call with a short chat history. A new `POST /query/stream` SSE endpoint sends `sources`, `token`s and `done`; the frontend reads it with `fetch` and renders citations and source chips.

**Tech Stack:** Python 3.12, FastAPI, LangGraph (ingestion workflow only), `langchain-google-genai`, Pinecone 10 (integrated inference + hosted rerank), `youtube-transcript-api`; Next.js 16 / React 19, `react-markdown`, Vitest (new, dev-only).

**Spec:** `docs/specs/2026-11-04-phase2-sources-streaming-design.md` (backend repo). Read it alongside this plan.

## Global Constraints

- Branch `feature/phase2-sources-streaming` in both repos; never commit to `main`.
- Every commit is authored by `Sanket Sonkusare <sanketsonkusare01@gmail.com>` (already set via `git config` in both clones) with **no** `Co-Authored-By` or other trailers.
- Backend: no new production dependencies. Remove `pyyaml` from `requirements.txt` and `pyproject.toml` once `promps.yml` is deleted (Task 8). Tests mock every external service; no API keys needed.
- Frontend: only new dependency is `vitest` as a devDependency.
- Spec values: chunk target 1000 chars, one-segment overlap; Gemini-text splitter `chunk_size=1000, chunk_overlap=100`; search `top_k=20`, rerank `top_n=6`; history keeps 6 exchanges; Gemini timeout 60 s; `start_seconds = -1` in Pinecone when unknown, `null` in the API; record id `"<video_id>-<n>"`; unknown video title `"YouTube video"`, channel `""`.
- Settings defaults: `RERANK_MODEL="bge-reranker-v2-m3"` (empty disables), `QUERY_MODEL="gemini-2.5-flash"`, `QUERY_THINKING_BUDGET=0`.
- Exact user-facing error strings: `"Couldn't search your videos. Please try again."` and `"The answer couldn't be completed. Please try again."`
- Progress event types and messages during ingestion stay unchanged.
- Backend tests: `cd AutoVoyce && .venv/bin/python -m pytest -q`. Frontend tests: `cd autovoyce_frontend && npx vitest run`; types: `npx tsc --noEmit -p .`.

## Review Focus

1. **Video titles containing quotes, brackets or Markdown** (e.g. `[Official] "Review" *2024*`) — the prompt's passage header and the source chips must show them literally without breaking formatting. Test: Task 6 `test_format_passages_keeps_odd_titles_literal`; Task 11 renders chips as plain text (no Markdown).
2. **Answers that contain real Markdown links or repeated markers** (`[docs](https://x)`, `[1][3]`, `[7]` with only 6 sources) — only valid bare `[n]` markers become citations. Test: Task 10 `linkCitations` cases.
3. **Multi-byte characters split across network chunks** (emoji, Hindi) in the stream — must not turn into `�`. Test: Task 9 `decodes UTF-8 split across chunks`.
4. **Caption lines with embedded newlines or extra spaces** (`"hello\nworld"`) — chunk text must read as normal prose. Test: Task 2 `test_whitespace_is_normalised`.
5. **Videos longer than an hour** — times show as `h:mm:ss` in both prompt and chip. Tests: Task 6 `test_format_time`; Task 10 `formatTimestamp`.

---

## File Map

Backend (`AutoVoyce/`):

| File | Change |
|---|---|
| `src/tools/transcript_fetcher.py` | Return segments; JSON cache; drop LangChain `@tool` wrapper |
| `src/tools/chunking.py` | **New.** `chunk_segments` |
| `src/tools/pinecone_uploader.py` | `build_records`, `upload_transcripts` (plain functions) |
| `src/utils/session_manager.py` | Per-session video metadata; cleanup calls `history.clear` |
| `src/schemas/response_schema.py` | New workflow state shape |
| `src/agents/youtube_transcript_agent.py`, `src/agents/pinecone_uploader_agent.py` | Use segments / per-video upload |
| `src/rag/__init__.py`, `retrieval.py`, `prompt.py`, `history.py`, `answer.py` | **New.** Search, prompt, history, answer streaming |
| `src/main/main.py` | `/upload` stores videos; `/upload/process` passes them; `/transcript` uses segments; `/query` and new `/query/stream` use `src/rag` |
| `settings.py` | `RERANK_MODEL`, `QUERY_MODEL`, `QUERY_THINKING_BUDGET` |
| `src/agents/pinecone_query_agent.py`, `src/tools/query_tool.py`, `src/utils/promps.yml` | **Delete** |
| `tests/fakes.py` | **New.** `FakeIndex`, `FakeChatModel` shared by tests |
| `README.md` | New settings, `/query/stream` |
| `docs/phase2-real-key-checklist.md` | **New.** Owner's real-service check |

Frontend (`autovoyce_frontend/`):

| File | Change |
|---|---|
| `lib/query-stream.ts` | **New.** `Source` type, SSE parser, `streamQuery` |
| `lib/citations.ts` | **New.** `citedNumbers`, `linkCitations`, `stripCitations`, `formatTimestamp` |
| `components/answer-with-citations.tsx` | **New.** Answer Markdown + citation badges + Sources chips + Context Used |
| `app/chat/page.tsx` | Streamed send flow; render assistant messages with the new component |
| `lib/config.ts` | `QUERY_STREAM` |
| `vitest.config.ts`, `package.json` | Vitest setup, `"test": "vitest run"` |

---

### Task 1: Transcripts as timestamped segments with a JSON cache

**Files:**
- Modify: `src/tools/transcript_fetcher.py`, `src/main/main.py` (`GET /transcript/{video_id}`, ~lines 120-150)
- Test: `tests/test_transcript_fetcher.py`

**Interfaces:**
- Produces:
  - `Segment = TypedDict("Segment", {"text": str, "start": float | None})` (in `transcript_fetcher.py`)
  - `get_transcript_from_captions(video_id: str) -> list[Segment]`
  - `get_transcript_from_gemini(video_id: str) -> list[Segment]` — one segment, `start=None`
  - `get_transcript_from_api(video_id: str) -> list[Segment]` — cache → sources per `TRANSCRIPT_SOURCE`; raises `Exception("No captions available: ...")` as today
  - `transcript_text(segments: list[Segment]) -> str` — texts joined with single spaces
  - `extract_video_id` unchanged. The `@tool transcript_fetcher` is removed (Task 4 calls `get_transcript_from_api` directly); keep the `__main__` CLI working via `get_transcript_from_api` + `transcript_text`.

- [ ] **Step 1: Write failing tests** (mock `YouTubeTranscriptApi` and `genai.Client`; set `TRANSCRIPT_CACHE_DIR` to `tmp_path` via `monkeypatch.setattr(settings, "TRANSCRIPT_CACHE_DIR", ...)`)

```python
def test_captions_become_segments_with_start(fake_ytt):  # fetch() returns raw data below
    fake_ytt.raw = [{"text": "hello", "start": 0.0, "duration": 1.5},
                    {"text": "  ", "start": 1.5, "duration": 1.0},
                    {"text": "world", "start": 2.5, "duration": 1.0}]
    assert get_transcript_from_captions("abcdefghijk") == [
        {"text": "hello", "start": 0.0}, {"text": "world", "start": 2.5}]  # blank line dropped

def test_gemini_returns_single_untimed_segment(fake_gemini):
    fake_gemini.text = "full transcript"
    assert get_transcript_from_gemini("abcdefghijk") == [{"text": "full transcript", "start": None}]

def test_cache_round_trip_as_json(tmp_cache, fake_ytt):
    first = get_transcript_from_api("abcdefghijk")
    fake_ytt.fail = True                       # second call must come from cache
    assert get_transcript_from_api("abcdefghijk") == first
    data = json.loads((tmp_cache / "abcdefghijk.json").read_text())
    assert data == {"source": "captions", "segments": first}

def test_old_txt_cache_is_ignored(tmp_cache, fake_ytt):
    (tmp_cache / "abcdefghijk.txt").write_text("stale text")
    assert get_transcript_from_api("abcdefghijk")[0]["text"] != "stale text"

def test_transcript_text_joins_segments():
    assert transcript_text([{"text": "a", "start": 0}, {"text": "b", "start": None}]) == "a b"

async def test_transcript_endpoint_shape(client, monkeypatch):
    # patch get_transcript_from_api -> two segments; GET /transcript/abcdefghijk
    # -> {"transcript": "a b", "video_id": "abcdefghijk", "segments": 2}
```

- [ ] **Step 2: Run** `pytest tests/test_transcript_fetcher.py -q` — expect failures (functions return strings / `.txt` cache).
- [ ] **Step 3: Implement.** Captions: `fetched.to_raw_data()`, strip each `text`, drop empty. Cache file `{video_id}.json` with `{"source", "segments"}`, same atomic temp-file write and same 11-char id guard as today; `_read_cache` returns `None` on missing/invalid JSON. `/transcript/{video_id}` returns `transcript_text(segments)` and `len(segments)`; 404 when the joined text is empty.
- [ ] **Step 4: Run** the whole suite — expect PASS.
- [ ] **Step 5: Commit** — `git commit -m "Keep caption timestamps: transcripts as segments with a JSON cache"`

---

### Task 2: Per-video chunking

**Files:**
- Create: `src/tools/chunking.py`
- Test: `tests/test_chunking.py`

**Interfaces:**
- Consumes: `Segment` (Task 1)
- Produces: `Chunk = TypedDict("Chunk", {"text": str, "start": float | None})`; `chunk_segments(segments: list[Segment], target_chars: int = 1000) -> list[Chunk]`

- [ ] **Step 1: Write failing tests**

```python
def seg(text, start): return {"text": text, "start": start}

def test_groups_segments_up_to_target_with_one_segment_overlap():
    segs = [seg("a" * 400, 0.0), seg("b" * 400, 10.0), seg("c" * 400, 20.0), seg("d" * 400, 30.0)]
    chunks = chunk_segments(segs, target_chars=1000)
    assert [c["start"] for c in chunks] == [0.0, 10.0, 20.0]
    assert chunks[0]["text"] == "a" * 400 + " " + "b" * 400
    assert chunks[1]["text"].startswith("b" * 400)      # overlap: last segment repeated
    assert all(len(c["text"]) <= 1000 for c in chunks)

def test_oversized_segment_is_its_own_chunk():
    chunks = chunk_segments([seg("x" * 1500, 5.0), seg("y", 9.0)], target_chars=1000)
    assert chunks[0] == {"text": "x" * 1500, "start": 5.0}

def test_untimed_text_uses_splitter_and_no_start():
    chunks = chunk_segments([seg("word " * 600, None)])
    assert len(chunks) >= 3 and all(c["start"] is None for c in chunks)
    assert all(len(c["text"]) <= 1000 for c in chunks)

def test_whitespace_is_normalised():                     # Review Focus 4
    assert chunk_segments([seg("hello\nworld  again", 1.0)]) == [{"text": "hello world again", "start": 1.0}]

def test_empty_input():
    assert chunk_segments([]) == []
```

- [ ] **Step 2: Run** `pytest tests/test_chunking.py -q` — expect `ModuleNotFoundError`.
- [ ] **Step 3: Implement `chunk_segments`.** Normalise each segment's text with `" ".join(text.split())`. If every segment has `start is None`, join texts and split with `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)` (use `target_chars` for `chunk_size`). Otherwise use the timed algorithm:

```
chunk = []                                  # segments in the current chunk
for s in segments:
    if chunk and len(joined(chunk + [s])) > target_chars:
        emit(chunk)                          # text = joined(chunk), start = chunk[0].start
        chunk = [chunk[-1]] if len(joined([chunk[-1], s])) <= target_chars else []
    chunk.append(s)
emit(chunk) if chunk
```

  Segments with `start is None` mixed into timed captions inherit the chunk's start.
- [ ] **Step 4: Run** — expect PASS.
- [ ] **Step 5: Commit** — `git commit -m "Add per-video, timestamp-aware chunking"`

---

### Task 3: Remember search results per session

**Files:**
- Modify: `src/utils/session_manager.py`, `src/main/main.py` (`/upload`)
- Test: `tests/test_session_videos.py`

**Interfaces:**
- Produces: `session_manager.set_videos(session_id: str, videos: list[dict]) -> None` (stores by `video["id"]`); `session_manager.get_video(session_id: str, video_id: str) -> dict | None`. Data is removed in `delete_session`.

- [ ] **Step 1: Write failing tests** (reuse the `fake_pinecone` fixture pattern from `tests/test_session_cleanup.py`)

```python
def test_videos_are_stored_and_looked_up(fake_pinecone):
    sid, _ = session_manager.create_session()
    session_manager.set_videos(sid, [{"id": "abcdefghijk", "title": "T", "channel": "C"}])
    assert session_manager.get_video(sid, "abcdefghijk")["title"] == "T"
    assert session_manager.get_video(sid, "zzzzzzzzzzz") is None

def test_videos_removed_with_session(fake_pinecone):
    sid, _ = session_manager.create_session()
    session_manager.set_videos(sid, [{"id": "abcdefghijk", "title": "T", "channel": "C"}])
    session_manager.delete_session(sid)
    assert session_manager.get_video(sid, "abcdefghijk") is None

async def test_upload_stores_search_results(client, monkeypatch):
    # patch retriever_agent_with_metadata -> [{"id": "abcdefghijk", "title": "T", "channel": "C", ...}]
    # POST /upload -> session_manager.get_video(session_id, "abcdefghijk")["channel"] == "C"
```

- [ ] **Step 2: Run** — expect `AttributeError: set_videos`.
- [ ] **Step 3: Implement.** A `_videos: Dict[str, Dict[str, dict]]` guarded by the existing `_lock`; popped in `delete_session`. `/upload` calls `set_videos` after the search.
- [ ] **Step 4: Run** the whole suite — expect PASS.
- [ ] **Step 5: Commit** — `git commit -m "Remember each session's search results for video titles"`

---

### Task 4: Ingestion stores per-video records

**Files:**
- Modify: `src/schemas/response_schema.py`, `src/agents/youtube_transcript_agent.py`, `src/agents/pinecone_uploader_agent.py`, `src/tools/pinecone_uploader.py`, `src/main/main.py` (`/upload/process` background function)
- Create: `tests/fakes.py`
- Test: `tests/test_ingestion.py`

**Interfaces:**
- Consumes: `get_transcript_from_api` (Task 1), `chunk_segments` (Task 2), `session_manager.get_video` (Task 3)
- Produces:
  - State (`ResponseSchema`, `total=False`): `videos: list[VideoInfo]` (`{"id", "title", "channel"}`), `transcripts: list[VideoTranscript]` (`{"video_id", "title", "channel", "segments"}`), `namespace: str`, `session_id: str`, `query_response: str | None`. Fields `user_query`, `video_ids`, `video_urls`, `transcript` are removed.
  - `pinecone_uploader.build_records(t: VideoTranscript) -> list[dict]` — records per spec §2.4
  - `pinecone_uploader.upload_transcripts(transcripts: list[VideoTranscript], namespace: str, session_id: str = "") -> int` — returns chunk count; emits the same events as today (`pinecone_upload_started`, `chunking_text`, `pinecone_uploading`, `chunks_uploaded`)
  - `tests/fakes.py: FakeIndex` with `upsert_records(namespace, records)`, `search(namespace, query, fields, rerank=None)`, `describe_index_stats()`, `delete_namespace(namespace)`, and attributes `records: dict[str, list[dict]]`, `search_calls: list[dict]`, `fail_rerank: bool`, `fail_search: bool`. Its `search` ranks by word overlap with `query["inputs"]["text"]`, honours `query["top_k"]`, then `rerank["top_n"]` when `rerank` is given, and returns `{"result": {"hits": [{"_id": ..., "fields": {...}}]}}` with only the requested fields. Every call is appended to `search_calls` as `{"namespace", "query", "fields", "rerank"}` (before any raise). `fail_rerank=True` raises only when `rerank` is passed; `fail_search=True` always raises.

- [ ] **Step 1: Write failing tests**

```python
def test_build_records_fields_and_ids():
    t = {"video_id": "abcdefghijk", "title": "T", "channel": "C",
         "segments": [{"text": "a" * 600, "start": 12.7}, {"text": "b" * 600, "start": 40.0}]}
    recs = build_records(t)
    assert [r["_id"] for r in recs] == ["abcdefghijk-0", "abcdefghijk-1"]
    assert recs[0] | {"chunk_text": None} == {"_id": "abcdefghijk-0", "chunk_text": None,
        "video_id": "abcdefghijk", "title": "T", "channel": "C", "start_seconds": 12}

def test_unknown_start_is_minus_one():
    t = {"video_id": "abcdefghijk", "title": "T", "channel": "C", "segments": [{"text": "x", "start": None}]}
    assert build_records(t)[0]["start_seconds"] == -1

def test_upload_batches_of_96(fake_index):
    # 200 timed segments of 990 chars -> 200 records -> 3 upsert calls, total 200

def test_workflow_uploads_each_video_with_titles(fake_index, monkeypatch):
    # patch get_transcript_from_api: "aaaaaaaaaa1" -> segments, "ccccccccccc" -> raises
    # processing_workflow.invoke({"videos": [{"id": "aaaaaaaaaa1", "title": "T1", "channel": "C1"},
    #     {"id": "ccccccccccc", "title": "T3", "channel": "C3"}], "namespace": "ns", "session_id": "s"})
    # -> all records in fake_index.records["ns"] have video_id "aaaaaaaaaa1", title "T1"
    # -> event types for "s" include "video_processed" and "video_error" (same messages as before)

async def test_process_endpoint_uses_session_titles(client, fake_index, monkeypatch):
    # session with set_videos([...title "T1"...]) + one id not in the search
    # POST /upload/process -> wait for processing_complete -> stored titles "T1" and "YouTube video"
```

- [ ] **Step 2: Run** — expect failures.
- [ ] **Step 3: Implement.** Transcript agent loops over `state["videos"]`, calling `get_transcript_from_api(video["id"])` and catching exceptions as `video_error` (keep today's event messages, which use the watch URL). Videos with empty `transcript_text` are errors. Uploader agent calls `upload_transcripts`, then emits `pinecone_upload_complete` as today. `/upload/process` builds `videos` from `get_video(...)`, falling back to `{"id": vid, "title": "YouTube video", "channel": ""}`. Drop the `@tool` decorator and `RecursiveCharacterTextSplitter` usage from `pinecone_uploader.py`.
- [ ] **Step 4: Run** the whole suite — expect PASS (update `tests/test_status_stream.py` only if it imports removed names).
- [ ] **Step 5: Commit** — `git commit -m "Store per-video chunks with title, channel and start time"`

---

### Task 5: Retrieval with rerank and fallback

**Files:**
- Create: `src/rag/__init__.py` (empty), `src/rag/retrieval.py`
- Modify: `settings.py`
- Test: `tests/test_retrieval.py`

**Interfaces:**
- Consumes: `FakeIndex` (Task 4)
- Produces:
  - `settings.RERANK_MODEL: str` (default `"bge-reranker-v2-m3"`), `settings.QUERY_MODEL` (default `"gemini-2.5-flash"`), `settings.QUERY_THINKING_BUDGET: int` (default `0`)
  - `@dataclass Passage(n: int, video_id: str, title: str, channel: str, start_seconds: int | None, text: str, url: str)` with `to_dict() -> dict` (keys exactly `n, video_id, title, channel, start_seconds, url, text`)
  - `video_url(video_id: str, start_seconds: int | None) -> str`
  - `build_search_text(question: str, previous_question: str | None) -> str`
  - `get_index()` — lazy Pinecone index (monkeypatch target in tests)
  - `search_passages(namespace: str, question: str, previous_question: str | None = None) -> list[Passage]`

- [ ] **Step 1: Write failing tests**

```python
def test_search_text():
    assert build_search_text("what about photos", None) == "what about photos"
    assert build_search_text("what about photos", "best phone?") == "best phone?\nwhat about photos"

def test_video_url():
    assert video_url("abcdefghijk", 272) == "https://www.youtube.com/watch?v=abcdefghijk&t=272s"
    assert video_url("abcdefghijk", None) == "https://www.youtube.com/watch?v=abcdefghijk"

def test_rerank_call_shape(fake_index, monkeypatch):
    monkeypatch.setattr(retrieval, "RERANK_MODEL", "bge-reranker-v2-m3")
    search_passages("ns", "photos?", "best phone?")
    call = fake_index.search_calls[0]
    assert call["query"] == {"inputs": {"text": "best phone?\nphotos?"}, "top_k": 20}
    assert call["rerank"] == {"model": "bge-reranker-v2-m3", "rank_fields": ["chunk_text"],
                              "top_n": 6, "query": "photos?"}
    assert set(call["fields"]) == {"chunk_text", "video_id", "title", "channel", "start_seconds"}

def test_falls_back_without_rerank_on_error(fake_index, monkeypatch):
    fake_index.fail_rerank = True            # 10 matching records in "ns"
    passages = search_passages("ns", "battery")
    assert len(passages) == 6 and fake_index.search_calls[-1]["rerank"] is None

def test_rerank_disabled_when_setting_empty(fake_index, monkeypatch):
    monkeypatch.setattr(retrieval, "RERANK_MODEL", "")
    search_passages("ns", "battery")
    assert len(fake_index.search_calls) == 1 and fake_index.search_calls[0]["rerank"] is None

def test_passages_numbered_with_urls_and_unknown_time(fake_index):
    # records: start_seconds 272 and -1
    p = search_passages("ns", "battery")
    assert [x.n for x in p] == list(range(1, len(p) + 1))
    assert any(x.start_seconds is None and "&t=" not in x.url for x in p)

def test_other_search_errors_propagate(fake_index):
    fake_index.fail_search = True
    with pytest.raises(Exception): search_passages("ns", "battery")
```

- [ ] **Step 2: Run** — expect `ModuleNotFoundError: src.rag`.
- [ ] **Step 3: Implement.** Call `get_index().search(namespace=..., query=..., fields=..., rerank=...)` (keyword names as in the test). Treat a missing field as `""`; `start_seconds < 0` → `None`; keep only hits with non-empty `chunk_text`; first 6. Log the rerank failure as a warning before falling back.
- [ ] **Step 4: Run** — expect PASS.
- [ ] **Step 5: Commit** — `git commit -m "Add retrieval: top 20, rerank to 6, fall back to plain search"`

---

### Task 6: Prompt and chat history

**Files:**
- Create: `src/rag/prompt.py`, `src/rag/history.py`
- Modify: `src/utils/session_manager.py` (`_free_session_memory`), `tests/test_session_cleanup.py`
- Test: `tests/test_prompt.py`, `tests/test_history.py`

**Interfaces:**
- Consumes: `Passage` (Task 5)
- Produces:
  - `prompt.SYSTEM_PROMPT: str` (the rules in spec §3.2)
  - `prompt.format_time(seconds: int) -> str` — `m:ss` under an hour, else `h:mm:ss`
  - `prompt.format_passages(passages: list[Passage]) -> str`
  - `prompt.build_user_message(question: str, passages: list[Passage]) -> str`
  - `history.MAX_EXCHANGES = 6`; `history.strip_citations(text: str) -> str`; `history.add_exchange(session_id: str, question: str, answer: str) -> None`; `history.get_history(session_id: str) -> list[tuple[str, str]]`; `history.clear(session_id: str) -> None`

- [ ] **Step 1: Write failing tests**

```python
def test_format_time():                                  # Review Focus 5
    assert format_time(0) == "0:00" and format_time(272) == "4:32" and format_time(3725) == "1:02:05"

def test_format_passages():
    text = format_passages([Passage(1, "v", "iPhone 15 Review", "MKBHD", 272, "body", "u"),
                            Passage(2, "w", "Pixel", "", None, "body2", "u2")])
    assert text == '[1] "iPhone 15 Review" by MKBHD, at 4:32\nbody\n\n[2] "Pixel"\nbody2'

def test_format_passages_keeps_odd_titles_literal():     # Review Focus 1
    out = format_passages([Passage(1, "v", '[Official] "Review" *2024*', "C", 5, "b", "u")])
    assert out.startswith('[1] "[Official] "Review" *2024*" by C, at 0:05')

def test_user_message_without_passages_says_so():
    msg = build_user_message("why?", [])
    assert "No passages" in msg and msg.rstrip().endswith("why?")

def test_system_prompt_rules():
    for phrase in ["[n]", "don't cover this", "not instructions"]:
        assert phrase in SYSTEM_PROMPT

def test_history_caps_and_strips():
    for i in range(8): history.add_exchange("s", f"q{i}", f"a{i} [1][2]")
    h = history.get_history("s")
    assert len(h) == 6 and h[0] == ("q2", "a2") and h[-1] == ("q7", "a7")

def test_strip_citations():
    assert history.strip_citations("Good [1]. Also [2][3] here.") == "Good. Also here."
    assert history.strip_citations("see [docs](https://x)") == "see [docs](https://x)"
```

  In `tests/test_session_cleanup.py`, replace the `_agent_cache` / `_checkpointer` assertions with: after `history.add_exchange(session_id, "q", "a")` and `delete_session`, `history.get_history(session_id) == []` (both tests).
- [ ] **Step 2: Run** — expect failures.
- [ ] **Step 3: Implement.** Passage header: `[n] "<title>"`, then ` by <channel>` if channel, then `, at <time>` if time; body on the next line; passages separated by a blank line. User message: `"Passages:\n\n<passages>\n\nQuestion: <question>"`, or `"No passages from the selected videos matched this question.\n\nQuestion: <question>"`. `strip_citations`: remove `\s*\[\d+\]` occurrences not followed by `(`, then tidy spaces before punctuation. History is a lock-guarded `dict[str, deque(maxlen=6)]`. `_free_session_memory` calls `history.clear(session_id)` instead of `forget_session`.
- [ ] **Step 4: Run** the whole suite — expect PASS.
- [ ] **Step 5: Commit** — `git commit -m "Add answer prompt and per-session chat history"`

---

### Task 7: Streamed answer generation

**Files:**
- Create: `src/rag/answer.py`
- Modify: `tests/fakes.py` (add `FakeChatModel`)
- Test: `tests/test_answer.py`

**Interfaces:**
- Consumes: `search_passages` (Task 5), `SYSTEM_PROMPT`, `build_user_message`, `history.*` (Task 6), settings (Task 5)
- Produces:
  - `SEARCH_ERROR_MESSAGE = "Couldn't search your videos. Please try again."`, `ANSWER_ERROR_MESSAGE = "The answer couldn't be completed. Please try again."`
  - `get_model()` — returns `ChatGoogleGenerativeAI(model=QUERY_MODEL, thinking_budget=QUERY_THINKING_BUDGET, timeout=60)`; monkeypatch target
  - `async def stream_answer(session_id: str, namespace: str, question: str, executor=None) -> AsyncIterator[dict]` — yields `{"type": "sources", "sources": [p.to_dict()...]}`, then `{"type": "token", "text": str}`..., then `{"type": "done", "answer": str}`; or `{"type": "error", "message": ...}` and stops
  - `class AnswerError(Exception)` — its message is the user-facing error string
  - `async def answer(session_id: str, namespace: str, question: str, executor=None) -> dict` — `{"response": str, "sources": list[dict]}`; raises `AnswerError(message)` on an `error` event
  - `tests/fakes.py: FakeChatModel(chunks: list[str | list[dict]], fail_after: int | None = None)` — a `BaseChatModel` whose `_astream` yields the given chunks (strings, or Gemini-style `[{"type": "text", "text": ...}]` lists) and raises after `fail_after` chunks; records the messages it received in `.calls`

- [ ] **Step 1: Write failing tests** (patch `answer.search_passages` and `answer.get_model`)

```python
async def collect(gen): return [e async for e in gen]

async def test_event_order_and_history_saved(fake_model):
    events = await collect(stream_answer("s", "ns", "battery?"))
    assert [e["type"] for e in events] == ["sources", "token", "token", "done"]
    assert events[-1]["answer"] == "Good [1]."
    assert history.get_history("s")[-1] == ("battery?", "Good.")

async def test_model_gets_system_history_and_passages(fake_model):
    history.add_exchange("s", "earlier q", "earlier a")
    await collect(stream_answer("s", "ns", "now?"))
    msgs = fake_model.calls[0]
    assert msgs[0].content == SYSTEM_PROMPT
    assert [m.content for m in msgs[1:3]] == ["earlier q", "earlier a"]
    assert "Question: now?" in msgs[-1].content
    # search_passages was called with previous_question="earlier q"

async def test_gemini_block_lists_are_flattened(fake_model_blocks):  # chunks as [{"type":"text","text":"Hi"}]
    events = await collect(stream_answer("s", "ns", "q"))
    assert events[-1]["answer"] == "Hi"

async def test_empty_sources_still_answers(no_passages, fake_model):
    events = await collect(stream_answer("s", "ns", "q"))
    assert events[0] == {"type": "sources", "sources": []} and events[-1]["type"] == "done"

async def test_search_failure_yields_error_only(failing_search):
    assert await collect(stream_answer("s", "ns", "q")) == [{"type": "error", "message": SEARCH_ERROR_MESSAGE}]

async def test_model_failure_after_tokens(fake_model_fail_after_1):
    events = await collect(stream_answer("s", "ns", "q"))
    assert [e["type"] for e in events] == ["sources", "token", "error"]
    assert events[-1]["message"] == ANSWER_ERROR_MESSAGE and history.get_history("s") == []

async def test_disconnect_does_not_save_history(fake_model):
    gen = stream_answer("s", "ns", "q")
    await gen.__anext__(); await gen.__anext__()        # sources + first token
    await gen.aclose()
    assert history.get_history("s") == []

async def test_answer_collects(fake_model):
    assert await answer("s", "ns", "q") == {"response": "Good [1].", "sources": [ ... ]}
```

- [ ] **Step 2: Run** — expect `ModuleNotFoundError`.
- [ ] **Step 3: Implement.** Search via `await loop.run_in_executor(executor, search_passages, namespace, question, previous_question)` where `previous_question` is the last history question or `None`. Messages: `SystemMessage(SYSTEM_PROMPT)`, then `HumanMessage`/`AIMessage` pairs from history, then `HumanMessage(build_user_message(...))`. Stream with `get_model().astream(messages)`; for each chunk keep only text (string content, or `text` of `type == "text"` blocks); skip empty. Log exceptions server-side. Save history only after the `done` event is yielded.
- [ ] **Step 4: Run** — expect PASS.
- [ ] **Step 5: Commit** — `git commit -m "Generate answers with one streamed model call"`

---

### Task 8: `/query/stream`, `/query` with sources, remove the old agent

**Files:**
- Modify: `src/main/main.py`, `README.md`, `requirements.txt`, `pyproject.toml`
- Delete: `src/agents/pinecone_query_agent.py`, `src/tools/query_tool.py`, `src/utils/promps.yml`
- Test: `tests/test_query_endpoints.py`

**Interfaces:**
- Consumes: `stream_answer`, `answer`, `AnswerError` (Task 7)
- Produces: `POST /query/stream` (spec §4.1); `POST /query` → `{"response", "namespace", "sources"}`; on `AnswerError` returns HTTP 502 `{"detail": <message>}`

- [ ] **Step 1: Write failing tests** (patch `main.stream_answer` / `main.answer` or the model + `FakeIndex`; parse with the `_parse` helper from `tests/test_status_stream.py`)

```python
async def test_stream_events_and_headers(client, live_session):
    resp = await client.post("/query/stream", json={"user_query": "battery?"}, headers={"X-Session-ID": live_session})
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert [e["type"] for e in _parse(resp.text)] == ["sources", "token", "token", "done"]

async def test_stream_unknown_session_is_404_json(client):
    resp = await client.post("/query/stream", json={"user_query": "hi", "session_id": "nope"})
    assert resp.status_code == 404 and resp.json()["detail"] == "Session not found or expired."

async def test_stream_validation_is_422(client):
    resp = await client.post("/query/stream", json={"user_query": "", "session_id": "x"})
    assert resp.status_code == 422

async def test_stream_error_event(client, live_session, failing_search):
    events = _parse((await client.post("/query/stream", json={"user_query": "q", "session_id": live_session})).text)
    assert events == [{"type": "error", "message": "Couldn't search your videos. Please try again."}]

async def test_query_returns_sources(client, live_session):
    body = (await client.post("/query", json={"user_query": "q", "session_id": live_session})).json()
    assert set(body) == {"response", "namespace", "sources"} and body["sources"][0]["n"] == 1

async def test_query_answer_error_is_502(client, live_session, failing_search):
    resp = await client.post("/query", json={"user_query": "q", "session_id": live_session})
    assert resp.status_code == 502
```

- [ ] **Step 2: Run** — expect 404 on `/query/stream`.
- [ ] **Step 3: Implement.** Shared helper `_resolve_session(request, x_session_id) -> (session_id, namespace)` raising today's 401/404. `/query/stream` returns `StreamingResponse` over `stream_answer(..., executor=_background_executor)`, each event as `data: <json>\n\n`, with the same headers as `/upload/status`. `/query` awaits `answer(...)`. Remove `query_agent` imports and the three deleted files; remove `pyyaml` from `requirements.txt` and `pyproject.toml`. README: document `/query/stream` events and the three settings.
- [ ] **Step 4: Run** the whole suite and `grep -rn "pinecone_query_agent\|query_tool\|promps" src tests` — expect PASS and no matches.
- [ ] **Step 5: Commit** — `git commit -m "Add /query/stream and return sources from /query"`, then `git push -u origin feature/phase2-sources-streaming`.

---

### Task 9: Frontend stream client (with Vitest setup)

Repo: `autovoyce_frontend`, branch `feature/phase2-sources-streaming`.

**Files:**
- Create: `lib/query-stream.ts`, `vitest.config.ts`, `lib/__tests__/query-stream.test.ts`
- Modify: `package.json` (devDependency `vitest`, script `"test": "vitest run"`), `lib/config.ts` (`QUERY_STREAM: \`${API_BASE_URL}/query/stream\``)

**Interfaces:**
- Produces:
  - `export interface Source { n: number; videoId: string; title: string; channel: string; startSeconds: number | null; url: string; text: string }`
  - `export class QueryStreamError extends Error { status?: number }`
  - `export function createSseParser(onData: (data: unknown) => void): { push(chunk: Uint8Array): void; end(): void }` — decodes with a streaming `TextDecoder`, splits events on blank lines, ignores `:` comment lines, `JSON.parse`s `data:` payloads
  - `export interface StreamHandlers { onSources(s: Source[]): void; onToken(t: string): void; onDone(answer: string): void; onError(message: string): void }`
  - `export function streamQuery(opts: { sessionId: string; query: string; signal?: AbortSignal } & StreamHandlers): Promise<void>` — throws `QueryStreamError` (message = server `detail` or status text, `status` set) on non-2xx; maps snake_case sources to `Source`; calls `onError("The answer stopped unexpectedly. Please try again.")` if the body ends without `done`/`error`

- [ ] **Step 1: Write failing tests** (`vitest.config.ts`: `resolve.alias { "@": path.resolve(__dirname) }`, `test.environment: "node"`)

```ts
const enc = (s: string) => new TextEncoder().encode(s)

it("parses events split across chunks and ignores keepalives", () => {
  const got: unknown[] = []; const p = createSseParser(d => got.push(d))
  p.push(enc('data: {"type":"tok')); p.push(enc('en","text":"a"}\n\n: keepalive\n\ndata: {"type":"done","answer":"a"}\n\n'))
  expect(got).toEqual([{ type: "token", text: "a" }, { type: "done", answer: "a" }])
})

it("decodes UTF-8 split across chunks", () => {           // Review Focus 3
  const bytes = enc('data: {"type":"token","text":"नमस्ते 👍"}\n\n'); const got: any[] = []
  const p = createSseParser(d => got.push(d)); p.push(bytes.slice(0, 30)); p.push(bytes.slice(30))
  expect(got[0].text).toBe("नमस्ते 👍")
})

it("calls handlers in order and maps sources", async () => {
  // mock global fetch -> ReadableStream of sources/token/done; expect onSources([{ n: 1, videoId: "abcdefghijk",
  // startSeconds: 272, ... }]), onToken("Hi"), onDone("Hi"); request has header X-Session-ID and body {"user_query": ...}
})

it("throws QueryStreamError with detail on 404", async () => {
  // fetch -> 404 {"detail":"Session not found or expired."} -> rejects with message equal to detail and status 404
})

it("reports a stream that ends without done", async () => {
  // body: sources + token only -> onError("The answer stopped unexpectedly. Please try again.")
})
```

- [ ] **Step 2: Run** `npm i -D vitest && npx vitest run` — expect failures (module missing).
- [ ] **Step 3: Implement** `lib/query-stream.ts` and the `QUERY_STREAM` config entry.
- [ ] **Step 4: Run** `npx vitest run && npx tsc --noEmit -p .` — expect PASS, no type errors.
- [ ] **Step 5: Commit** — `git commit -m "Add streaming query client with Vitest tests"`

---

### Task 10: Citation helpers

**Files:**
- Create: `lib/citations.ts`, `lib/__tests__/citations.test.ts`

**Interfaces:**
- Consumes: `Source` (Task 9)
- Produces: `citedNumbers(text: string, sources: Source[]): number[]`; `linkCitations(text: string, sources: Source[]): string`; `stripCitations(text: string): string`; `formatTimestamp(seconds: number): string`

- [ ] **Step 1: Write failing tests**

```ts
const src = (n: number) => ({ n, videoId: "v", title: "t", channel: "c", startSeconds: 1, url: `u${n}`, text: "" })
const six = [1, 2, 3, 4, 5, 6].map(src)

it("citedNumbers: valid, ordered by first use, unique", () => {
  expect(citedNumbers("a [3] b [1][3] c [9]", six)).toEqual([3, 1])
})
it("linkCitations: bare markers only", () => {             // Review Focus 2
  expect(linkCitations("x [1][3] y [7] see [docs](https://x) and [2](https://y)", six))
    .toBe("x [1](#cite-1)[3](#cite-3) y [7] see [docs](https://x) and [2](https://y)")
})
it("stripCitations", () => {
  expect(stripCitations("Good [1]. Also [2][3] here.")).toBe("Good. Also here.")
})
it("formatTimestamp", () => {                              // Review Focus 5
  expect(formatTimestamp(272)).toBe("4:32"); expect(formatTimestamp(3725)).toBe("1:02:05")
})
```

- [ ] **Step 2: Run** `npx vitest run lib/__tests__/citations.test.ts` — expect failures.
- [ ] **Step 3: Implement.** A marker is `\[(\d+)\]` not followed by `(`; valid when a source with that `n` exists. `stripCitations` matches the backend's `history.strip_citations` behaviour.
- [ ] **Step 4: Run** `npx vitest run` — expect PASS.
- [ ] **Step 5: Commit** — `git commit -m "Add citation helpers"`

---

### Task 11: Streamed chat UI with citations and source chips

**Files:**
- Create: `components/answer-with-citations.tsx`
- Modify: `app/chat/page.tsx` (`Message`/`SourceReference` types ~lines 24-38; `handleSendMessageWithText` ~531-712; message rendering ~760-965)

**Interfaces:**
- Consumes: `streamQuery`, `Source`, `QueryStreamError` (Task 9); citation helpers (Task 10)
- Produces: `export function AnswerWithCitations(props: { content: string; sources: Source[]; error?: string }): JSX.Element`

- [ ] **Step 1: Build the component.** Move the existing assistant `ReactMarkdown` block and its `components` styling (page ~772-895) into it, rendering `linkCitations(content, sources)`. The `a` renderer: `href` matching `#cite-<n>` renders a small superscript badge `<n>` linking to that source's `url` (`target="_blank" rel="noopener noreferrer"`); other links keep today's style. Below: **Sources** list for `citedNumbers(content, sources)` — each chip `[n] ▶ {title} · {channel}   {formatTimestamp(startSeconds)}` as plain text (no Markdown), opening `url` in a new tab; `· channel` omitted when empty, time omitted when `startSeconds` is `null`; chips wrap, titles truncate. **Context Used** (existing collapsible panel and its local open state, moved here) lists the cited sources' `text`. `error` renders as a small red line under the text.
- [ ] **Step 2: Rewrite the send flow in `handleSendMessageWithText`.** Keep session lookup and the user-message append. Then: create an assistant message `{ id, role: "assistant", content: "", sources: [], timestamp }` and append it; call `streamQuery` with handlers that update that message by id (`onSources` sets `sources`; `onToken` appends; `onDone` sets final `content`; `onError` sets `error`) and turn off `isTyping` on the first token, `done` or `error`. Catch `QueryStreamError`: keep today's 401/404 "Please upload videos first from the Ingestion page." suffix. After `done`, if voice input was used, `speak(stripCitations(answer))` with today's flag handling. Remove the duplicate-response check. Hide an assistant bubble while its content is empty and it has no error (the typing dots show instead). Keep one `AbortController` in a ref; abort it in the existing unmount cleanup.
- [ ] **Step 3: Update types and rendering.** `Message.sources?: Source[]`, `Message.error?: string`; delete `SourceReference`, `contextUsed`, `showContext` and `toggleContext`. Assistant messages render `<AnswerWithCitations content sources error />`; user messages unchanged.
- [ ] **Step 4: Verify** `npx tsc --noEmit -p . && npx vitest run && NEXT_PUBLIC_API_URL=http://localhost:8000 npx next build` — expect no type errors, tests PASS, build succeeds.
- [ ] **Step 5: Commit** — `git commit -m "Stream chat answers with citations and source chips"`, then `git push -u origin feature/phase2-sources-streaming`.

---

### Task 12: End-to-end check and real-key checklist

**Files:**
- Create (backend repo): `docs/phase2-real-key-checklist.md`
- Scratch only (not committed): update the Phase 1 harness `run_backend.py` in the session scratchpad so its fakes match the new code — `FakeIndex` stores record fields and honours `rerank`; fake transcripts return timed segments; fake model streams several tokens with `[1]` markers via `_astream`, and answers "The selected videos don't cover this, but…" with no markers when the question contains "weather".

- [ ] **Step 1: Run the backend harness and `npx next start`; drive Chromium (Playwright)** through: search → select 3 videos (one without captions) → ingest → chat. Expected:
  - The answer text grows across at least two DOM snapshots before completion.
  - Each citation badge and chip `href` equals `https://www.youtube.com/watch?v=<id>&t=<start>s` of the cited record.
  - Context Used shows the cited passage text.
  - The "weather" question shows the labelled answer and no Sources list.
  - No requests to `:8000` fail; no console errors other than the Vercel Analytics 404.
  - Screenshot of a cited answer at 1280px and at 390px width (chips wrap, no horizontal scroll).
- [ ] **Step 2: Write `docs/phase2-real-key-checklist.md`**: `.env` keys needed, commands to start backend (`uv run uvicorn src.main.main:app --port 8000`) and frontend (`NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`), then checks: a captions video ingests; a backend log line shows rerank used (or the fallback warning); a question streams; badge/chip opens YouTube at the quoted moment; a follow-up keeps context; an off-topic question is labelled; a voice question is spoken without "bracket one"; `RERANK_MODEL=` (empty) still answers.
- [ ] **Step 3: Commit and push** the checklist (backend repo) — `git commit -m "Add Phase 2 real-key checklist"`.
- [ ] **Step 4: Report** results and screenshots to the owner. Merging to `main` waits for their real-key check.

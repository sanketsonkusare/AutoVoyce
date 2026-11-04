# Phase 2 real-key check

The automated tests and the local browser run use fake YouTube, Pinecone and
Gemini services. This check runs Phase 2 once against the real services
before it is merged to `main`. It takes about 10 minutes.

## 1. Get both branches

```bash
cd AutoVoyce && git fetch origin && git checkout feature/phase2-sources-streaming && git pull
```

```bash
cd autovoyce_frontend && git fetch origin && git checkout feature/phase2-sources-streaming && git pull && npm install
```

## 2. Start the backend

`AutoVoyce/.env` needs the same keys as production: `GOOGLE_API_KEY`,
`SERP_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`,
`PINECONE_HOST_URL`, plus your transcript proxy settings if you use them.
The new settings (`RERANK_MODEL`, `QUERY_MODEL`, `QUERY_THINKING_BUDGET`)
can stay unset.

```bash
cd AutoVoyce && uv sync && uv run uvicorn src.main.main:app --port 8000
```

## 3. Start the frontend (second terminal)

```bash
cd autovoyce_frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000/ingestion.

## 4. Checks

| # | Do this | Expected |
|---|---|---|
| 1 | Search a topic (e.g. "iphone 15 battery review"), select 2–3 videos, start ingestion | Progress log as before; "Processing Complete!" |
| 2 | Watch the backend terminal during ingestion | `Got transcript for … from YouTube captions` (or the Gemini fallback) and `Uploaded N chunks …` |
| 3 | Go to Chat, ask a question the videos answer | Text appears word by word, with small numbered badges |
| 4 | Look at the backend terminal after that question | **No** `Rerank search failed` warning → reranking worked. If the warning appears, answers still work (plain search fallback); check your Pinecone plan's rerank quota |
| 5 | Click a badge and a source chip | YouTube opens in a new tab at the moment the cited point is made (within a few seconds) |
| 6 | Open "Context Used" | Shows the passages behind the cited numbers |
| 7 | Ask a follow-up like "what about the camera?" | Answer stays on the same videos/topic |
| 8 | Ask something unrelated, e.g. "what's the weather in Paris?" | Starts with "The selected videos don't cover this, but…", no source chips |
| 9 | Use the mic to ask a question (Chrome/Edge) | Answer is read aloud without saying the numbers in brackets |
| 10 | Stop the backend, restart it with `RERANK_MODEL=` (empty), ingest again and ask | Answers still work (reranking off) |
| 11 | Optional, in Pinecone console | Records in the `session_…` namespace have `video_id`, `title`, `channel`, `start_seconds` |

If anything fails, copy the backend terminal output around the failure and
the browser console error.

## 5. Deploy order after the check

1. Merge and deploy the backend first. The current frontend keeps working,
   because `/query` is unchanged apart from an added `sources` field.
2. Then merge and deploy the frontend.

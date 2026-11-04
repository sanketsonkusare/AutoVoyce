# AutoVoyce Backend

FastAPI backend application that processes YouTube videos, extracts transcripts, and stores them in Pinecone for querying.

## Prerequisites

- Python 3.12 or higher
- `uv` package manager (install from https://github.com/astral-sh/uv)

## Setup Instructions

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or on macOS with Homebrew:

```bash
brew install uv
```

### 2. Install Dependencies

```bash
cd backend
uv sync
```

This will install all dependencies specified in `pyproject.toml` and create a virtual environment.

### 3. Create Environment File

Create a `.env` file in the `backend/` directory with the following variables:

```env
GOOGLE_API_KEY=your_google_api_key_here
SERP_API_KEY=your_serp_api_key_here
SEARCH_LIMIT=10
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=your_pinecone_index_name
PINECONE_HOST_URL=your_pinecone_host_url
```

**Note:** Replace all placeholder values with your actual API keys and configuration.

Optional settings for chat answers (the defaults work as-is):

```env
RERANK_MODEL=bge-reranker-v2-m3   # Pinecone hosted reranker; set empty to turn reranking off
QUERY_MODEL=gemini-2.5-flash      # Gemini model that writes answers
QUERY_THINKING_BUDGET=0           # Gemini thinking tokens before answering (0 = fastest)
```

Reranking has a monthly limit on Pinecone's free plan. When a rerank call
fails, search falls back to plain similarity automatically.

### 4. Activate Virtual Environment

```bash
source .venv/bin/activate
```

Or if using uv directly:

```bash
uv run <command>
```

## Running the Application

### Option 1: Run with uvicorn directly

```bash
uv run uvicorn src.main.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option 2: Run the main.py file directly

```bash
uv run python src/main/main.py
```

### Option 3: Use uv to run

```bash
uv run python -m uvicorn src.main.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

Once the server is running, you can access:

- **Health Check**: `GET http://localhost:8000/`
- **API Documentation**: `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs**: `http://localhost:8000/redoc` (ReDoc)

### Available Endpoints

1. **POST /upload**

   - Uploads YouTube videos based on a query
   - Request body: `{"user_query": "your search query"}`
   - Example:
     ```bash
     curl -X POST "http://localhost:8000/upload" \
          -H "Content-Type: application/json" \
          -d '{"user_query": "best value for money iphones"}'
     ```

2. **POST /query**
   - Answers a question about the session's videos (not streamed)
   - Response: `{"response": "...[1]...", "namespace": "...", "sources": [...]}`; each `[n]`
     in the answer refers to the source with that `n` (see `/query/stream` below)
   - Request body: `{"user_query": "your question", "session_id": "<id from /upload>"}`
     (or send the id in an `X-Session-ID` header). There is no session cookie.
   - Example:
     ```bash
     curl -X POST "http://localhost:8000/query" \
          -H "Content-Type: application/json" \
          -d '{"user_query": "What are the best iPhones?", "session_id": "<session_id>"}'
     ```

3. **POST /query/stream**
   - Same request as `/query`; the answer arrives as server-sent events
     (one `data: {json}` line per event):
     - `{"type": "sources", "sources": [{"n", "video_id", "title", "channel", "start_seconds", "url", "text"}]}` (first)
     - `{"type": "token", "text": "..."}` (many)
     - `{"type": "done", "answer": "..."}` (last), or `{"type": "error", "message": "..."}`
   - `url` opens the video at `start_seconds` (`null` when unknown)
   - Both query endpoints return `409` with a readable `detail` while the session's
     videos are still processing, or if none have been processed yet
   - Example:
     ```bash
     curl -N -X POST "http://localhost:8000/query/stream" \
          -H "Content-Type: application/json" \
          -d '{"user_query": "Which phone has the best battery?", "session_id": "<session_id>"}'
     ```

## Development

### Running Tests

Tests mock Pinecone, Gemini and SerpAPI, so they need no API keys:

```bash
uv sync --group dev
uv run pytest
```

### Project Structure

```
backend/
├── src/
│   ├── agents/          # Ingestion workflow steps
│   ├── main/            # FastAPI application
│   ├── rag/             # Search, prompt, chat history and answer streaming
│   ├── schemas/         # Pydantic schemas
│   ├── tools/           # Custom tools
│   ├── utils/           # Utilities and helpers
│   └── workflow/        # LangGraph workflow
├── settings.py          # Configuration settings
├── pyproject.toml       # Project dependencies
└── .env                 # Environment variables (create this)
```

## Troubleshooting

- **Import errors**: Make sure you've activated the virtual environment or are using `uv run`
- **API key errors**: Verify all environment variables are set correctly in `.env`
- **Port already in use**: Change the port in the uvicorn command (e.g., `--port 8001`)
- **CORS errors**: The backend is configured to allow requests from `http://localhost:3000` (frontend)


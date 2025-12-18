# AutoVoyce

AutoVoyce is a FastAPI application that processes YouTube videos, extracts transcripts, and stores them in Pinecone for querying.

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
uv sync
```

This will install all dependencies specified in `pyproject.toml` and create a virtual environment.

### 3. Create Environment File

Create a `.env` file in the project root with the following variables:

```env
GOOGLE_API_KEY=your_google_api_key_here
GROQ_API_KEY=your_groq_api_key_here
SERP_API_KEY=your_serp_api_key_here
SEARCH_LIMIT=10
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=your_pinecone_index_name
PINECONE_HOST_URL=your_pinecone_host_url
```

**Note:** Replace all placeholder values with your actual API keys and configuration.

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
   - Queries the Pinecone knowledge base
   - Request body: `{"user_query": "your question"}`
   - Example:
     ```bash
     curl -X POST "http://localhost:8000/query" \
          -H "Content-Type: application/json" \
          -d '{"user_query": "What are the best iPhones?"}'
     ```

## Development

### Running Tests

If you have tests, you can run them with:

```bash
uv run pytest
```

### Project Structure

```
AutoVoyce/
├── src/
│   ├── agents/          # LangChain agents
│   ├── main/            # FastAPI application
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

import os
import sys
from pathlib import Path

# Make the repo root importable (settings.py, src/...)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Dummy config so modules import without a real .env
os.environ.setdefault("GOOGLE_API_KEY", "test")
os.environ.setdefault("SERP_API_KEY", "test")
os.environ.setdefault("PINECONE_API_KEY", "test")
os.environ.setdefault("PINECONE_HOST_URL", "https://example.invalid")
os.environ.setdefault("PINECONE_INDEX_NAME", "test")
os.environ.setdefault("TRANSCRIPT_CACHE_DIR", "")


import pytest  # noqa: E402


@pytest.fixture
def fake_index(monkeypatch):
    """A FakeIndex wired into every module that talks to Pinecone."""
    from tests.fakes import FakeIndex
    from src.tools import pinecone_uploader

    index = FakeIndex()
    monkeypatch.setattr(pinecone_uploader, "_get_index", lambda: index)
    monkeypatch.setattr(pinecone_uploader, "_INDEX_SETTLE_SECONDS", 0)
    from src.rag import retrieval
    monkeypatch.setattr(retrieval, "get_index", lambda: index)
    return index

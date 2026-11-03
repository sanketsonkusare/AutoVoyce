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

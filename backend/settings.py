from dotenv import load_dotenv
from os import getenv
from pathlib import Path

load_dotenv(".env")

BASE_DIR = Path(__file__).resolve().parent

GOOGLE_API_KEY = getenv("GOOGLE_API_KEY")
GROQ_API_KEY = getenv("GROQ_API_KEY")
SERP_API_KEY = getenv("SERP_API_KEY")
SEARCH_LIMIT = int(getenv("SEARCH_LIMIT", "10"))
PINECONE_API_KEY = getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = getenv("PINECONE_INDEX_NAME")
PINECONE_HOST_URL = getenv("PINECONE_HOST_URL")
NAMESPACE = "youtube_transcripts"
DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes - increased to allow time for processing and querying

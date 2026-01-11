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
ELEVENLABS_API_KEY = getenv("ELEVENLABS_API_KEY")
NAMESPACE = "youtube_transcripts"
DEFAULT_TIMEOUT_SECONDS = 43200  # 12 hours (12 * 60 * 60)

# YouTube cookies for yt-dlp authentication
# Option 1: Direct file path (local development)
# Option 2: Content from env var (Railway/production) - written to temp file
YOUTUBE_COOKIES_PATH = getenv("YOUTUBE_COOKIES_PATH", "")
YOUTUBE_COOKIES_CONTENT = getenv("YOUTUBE_COOKIES_CONTENT", "")

# If cookies content is provided but no path, create a temp file
if YOUTUBE_COOKIES_CONTENT and not YOUTUBE_COOKIES_PATH:
    import tempfile
    cookies_file = Path(tempfile.gettempdir()) / "youtube_cookies.txt"
    cookies_file.write_text(YOUTUBE_COOKIES_CONTENT)
    YOUTUBE_COOKIES_PATH = str(cookies_file)
    print(f"🍪 Created cookies file at: {YOUTUBE_COOKIES_PATH}")

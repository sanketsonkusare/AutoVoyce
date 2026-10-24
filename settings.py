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

# Webshare rotating proxy credentials (for youtube-transcript-api rate limit bypass)
# Get these from: https://www.webshare.io/ (Residential proxy package)
WEBSHARE_PROXY_USERNAME = getenv("WEBSHARE_PROXY_USERNAME", "")
WEBSHARE_PROXY_PASSWORD = getenv("WEBSHARE_PROXY_PASSWORD", "")

# Your own proxy for YouTube caption requests, e.g. a phone at home reached via
# Tailscale: http://100.x.y.z:8080 (or http://user:pass@100.x.y.z:8080).
# Takes priority over Webshare. Leave empty to disable.
TRANSCRIPT_PROXY_URL = getenv("TRANSCRIPT_PROXY_URL", "").strip()
# Seconds to wait for each request before giving up (so a sleeping phone fails fast)
TRANSCRIPT_PROXY_TIMEOUT = float(getenv("TRANSCRIPT_PROXY_TIMEOUT", "20"))

# Transcript source: "auto" (captions, then Gemini), "gemini", or "captions".
# On a cloud server YouTube blocks caption requests, so use "gemini" there.
TRANSCRIPT_SOURCE = getenv("TRANSCRIPT_SOURCE", "auto").strip().lower()
if TRANSCRIPT_SOURCE not in ("auto", "gemini", "captions"):
    TRANSCRIPT_SOURCE = "auto"

# Gemini model used to transcribe YouTube links
GEMINI_TRANSCRIPT_MODEL = getenv("GEMINI_TRANSCRIPT_MODEL", "gemini-2.5-flash")

# Folder where transcripts are cached (empty string disables the cache)
TRANSCRIPT_CACHE_DIR = getenv("TRANSCRIPT_CACHE_DIR", str(BASE_DIR / ".cache" / "transcripts"))

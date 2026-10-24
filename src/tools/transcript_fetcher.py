from langchain.tools import tool
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from pathlib import Path
import re
import time
import logging
import requests

logger = logging.getLogger("autovoyce.transcript")

# Gemini replies with this exact text when a video has no speech.
NO_SPEECH_MARKER = "NO_SPEECH"

GEMINI_TRANSCRIPT_PROMPT = (
    "Transcribe all spoken words in this video as plain text. "
    "If the speech is not in English, translate it to English. "
    "Do not add timestamps, speaker labels, headings, summaries or comments. "
    f"If the video has no speech, reply with exactly: {NO_SPEECH_MARKER}"
)


def extract_video_id(video_url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
            return match.group(1)
    return video_url  # Return as-is if no pattern matches


# --- Cache -------------------------------------------------------------------
# Each transcript is saved once, so a video is never fetched twice.
# Cache errors never break a request: the cache is only a speed-up.

def _cache_file(video_id: str) -> Path | None:
    from settings import TRANSCRIPT_CACHE_DIR
    if not TRANSCRIPT_CACHE_DIR:
        return None
    if not re.fullmatch(r"[a-zA-Z0-9_-]{11}", video_id):
        return None  # Only cache real video IDs (also blocks path tricks)
    return Path(TRANSCRIPT_CACHE_DIR) / f"{video_id}.txt"


def _read_cache(video_id: str) -> str | None:
    path = _cache_file(video_id)
    try:
        if path and path.is_file():
            text = path.read_text(encoding="utf-8")
            if text.strip():
                return text
    except OSError as e:
        logger.warning(f"Could not read transcript cache for {video_id}: {e}")
    return None


def _write_cache(video_id: str, text: str) -> None:
    path = _cache_file(video_id)
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)  # Atomic rename: no half-written files
    except OSError as e:
        logger.warning(f"Could not write transcript cache for {video_id}: {e}")


# --- Source 1: YouTube captions ------------------------------------------------

class _TimeoutSession(requests.Session):
    """requests.Session with a default timeout, so a dead proxy fails fast."""

    def __init__(self, timeout: float):
        super().__init__()
        self._timeout = timeout

    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return super().request(*args, **kwargs)


def get_transcript_from_captions(video_id: str) -> str:
    """
    Fetch transcript using YouTube's caption API (youtube-transcript-api).

    Proxy choice, in order:
      1. TRANSCRIPT_PROXY_URL (your own proxy, e.g. a phone at home via Tailscale)
      2. Webshare residential proxy, if credentials are set
      3. Direct connection
    Note: YouTube blocks most cloud server IPs, so a direct fetch often fails on a VPS.
    """
    from settings import (
        WEBSHARE_PROXY_USERNAME,
        WEBSHARE_PROXY_PASSWORD,
        TRANSCRIPT_PROXY_URL,
        TRANSCRIPT_PROXY_TIMEOUT,
    )

    try:
        http_client = _TimeoutSession(TRANSCRIPT_PROXY_TIMEOUT)
        if TRANSCRIPT_PROXY_URL:
            from youtube_transcript_api.proxies import GenericProxyConfig
            # Don't log the URL: it may contain a username and password.
            logger.info("Using custom proxy (TRANSCRIPT_PROXY_URL)")
            ytt_api = YouTubeTranscriptApi(
                proxy_config=GenericProxyConfig(
                    http_url=TRANSCRIPT_PROXY_URL,
                    https_url=TRANSCRIPT_PROXY_URL,
                ),
                http_client=http_client,
            )
        elif WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD:
            from youtube_transcript_api.proxies import WebshareProxyConfig
            logger.info("Using Webshare rotating residential proxies")
            ytt_api = YouTubeTranscriptApi(
                proxy_config=WebshareProxyConfig(
                    proxy_username=WEBSHARE_PROXY_USERNAME,
                    proxy_password=WEBSHARE_PROXY_PASSWORD,
                ),
                http_client=http_client,
            )
        else:
            ytt_api = YouTubeTranscriptApi(http_client=http_client)

        # Primary: Use simple fetch() — tries English by default
        try:
            fetched = ytt_api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
            formatter = TextFormatter()
            return formatter.format_transcript(fetched)
        except Exception:
            pass

        # Fallback: List transcripts and find any available one
        transcript_list = ytt_api.list(video_id)

        # Prefer manual transcripts, fall back to auto-generated
        try:
            transcript = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
            except Exception:
                # Try any available transcript
                transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])

        fetched = transcript.fetch()
        formatter = TextFormatter()
        return formatter.format_transcript(fetched)

    except Exception as e:
        raise Exception(f"No captions available: {str(e)}")


# --- Source 2: Gemini reads the YouTube link ------------------------------------

def get_transcript_from_gemini(video_id: str) -> str:
    """
    Ask Gemini to transcribe a public YouTube video from its URL.

    Google's servers fetch the video, so YouTube's block on cloud IPs does not
    apply. Free tier limit (preview feature): about 8 hours of YouTube video
    per day. Only public videos work.
    """
    from google import genai
    from google.genai import types, errors
    from settings import GOOGLE_API_KEY, GEMINI_TRANSCRIPT_MODEL

    if not GOOGLE_API_KEY:
        raise Exception("Gemini transcription unavailable: GOOGLE_API_KEY is not set")

    client = genai.Client(api_key=GOOGLE_API_KEY)
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    contents = types.Content(
        role="user",
        parts=[
            types.Part(file_data=types.FileData(file_uri=video_url)),
            types.Part(text=GEMINI_TRANSCRIPT_PROMPT),
        ],
    )
    config = types.GenerateContentConfig(
        temperature=0,
        # Low resolution: ~100 tokens per second of video instead of ~300.
        # Frames barely matter for a transcript; the audio is what counts.
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
        # No "thinking" needed to write down speech; saves tokens and time.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        http_options=types.HttpOptions(timeout=300_000),  # 5 minutes, in ms
    )

    # Retry on rate limits (429) and temporary server errors (5xx).
    waits = [15, 45]
    for attempt in range(len(waits) + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_TRANSCRIPT_MODEL, contents=contents, config=config
            )
            text = (response.text or "").strip()
            if not text or text == NO_SPEECH_MARKER:
                raise Exception("Gemini found no speech in this video")
            return text
        except errors.APIError as e:
            retryable = e.code == 429 or (e.code is not None and e.code >= 500)
            if retryable and attempt < len(waits):
                logger.warning(
                    f"Gemini error {e.code} for {video_id}; retrying in {waits[attempt]}s"
                )
                time.sleep(waits[attempt])
                continue
            raise Exception(f"Gemini transcription failed ({e.code}): {e.message}")

    raise Exception("Gemini transcription failed after retries")


# --- Main entry point ------------------------------------------------------------

def get_transcript_from_api(video_id: str) -> str:
    """
    Get a transcript for a video, trying sources in order.

    TRANSCRIPT_SOURCE setting:
      - "auto" (default): cache -> YouTube captions -> Gemini
      - "gemini":         cache -> Gemini (best on a cloud server)
      - "captions":       cache -> YouTube captions only
    """
    from settings import TRANSCRIPT_SOURCE

    cached = _read_cache(video_id)
    if cached:
        logger.info(f"Transcript cache hit for {video_id}")
        return cached

    errors_seen = []

    if TRANSCRIPT_SOURCE in ("auto", "captions"):
        try:
            text = get_transcript_from_captions(video_id)
            logger.info(f"Got transcript for {video_id} from YouTube captions")
            _write_cache(video_id, text)
            return text
        except Exception as e:
            errors_seen.append(str(e))
            if TRANSCRIPT_SOURCE == "captions":
                raise
            logger.warning(f"Captions failed for {video_id}; falling back to Gemini")

    if TRANSCRIPT_SOURCE in ("auto", "gemini"):
        try:
            logger.info(f"Transcribing {video_id} with Gemini...")
            started = time.monotonic()
            text = get_transcript_from_gemini(video_id)
            logger.info(
                f"Got transcript for {video_id} from Gemini "
                f"({len(text)} chars in {time.monotonic() - started:.0f}s)"
            )
            _write_cache(video_id, text)
            return text
        except Exception as e:
            errors_seen.append(str(e))

    # Keep the "No captions available" prefix: main.py maps it to HTTP 404.
    raise Exception("No captions available: " + " | ".join(errors_seen))


@tool
def transcript_fetcher(video_url: str) -> str:
    """
    Fetches transcript for a YouTube video (captions, with Gemini as fallback).

    Args:
        video_url (str): The URL of the YouTube video.

    Returns:
        str: The full transcript text.
    """
    video_id = extract_video_id(video_url)
    logger.info(f"Processing video: {video_id}")

    try:
        logger.info("Fetching transcript...")
        transcript = get_transcript_from_api(video_id)
        logger.info("Got transcript")
        return transcript
    except Exception as e:
        error_msg = f"Error: Could not get transcript. {str(e)}"
        logger.warning(error_msg)
        return error_msg


# --- Usage ---
# Test one video from the repo root:
#   TRANSCRIPT_SOURCE=gemini uv run python -m src.tools.transcript_fetcher 9GSDvO0LFFE
if __name__ == "__main__":
    import sys
    from settings import TRANSCRIPT_SOURCE

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    target = sys.argv[1] if len(sys.argv) > 1 else "9GSDvO0LFFE"
    print(f"Source: {TRANSCRIPT_SOURCE}")
    started = time.monotonic()
    transcript = transcript_fetcher.invoke({"video_url": target})
    print(f"\n--- Transcript ({len(transcript)} chars, {time.monotonic() - started:.0f}s) ---\n")
    print(transcript[:1500] + ("\n..." if len(transcript) > 1500 else ""))

from langchain.tools import tool
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import re
import logging

logger = logging.getLogger("autovoyce.transcript")

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


def get_transcript_from_api(video_id: str) -> str:
    """
    Fetch transcript using YouTube's caption API (youtube-transcript-api v1.2.4).
    
    Uses Webshare residential proxy if credentials are available in settings.
    Falls back to direct connection if no proxy is configured.
    """
    from settings import WEBSHARE_PROXY_USERNAME, WEBSHARE_PROXY_PASSWORD
    
    try:
        # Initialize API — with proxy if credentials are available
        if WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD:
            from youtube_transcript_api.proxies import WebshareProxyConfig
            logger.info("Using Webshare rotating residential proxies")
            ytt_api = YouTubeTranscriptApi(
                proxy_config=WebshareProxyConfig(
                    proxy_username=WEBSHARE_PROXY_USERNAME,
                    proxy_password=WEBSHARE_PROXY_PASSWORD,
                )
            )
        else:
            ytt_api = YouTubeTranscriptApi()
        
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


@tool
def transcript_fetcher(video_url: str) -> str:
    """
    Fetches transcript for a YouTube video using the YouTube Caption API.
    
    Args:
        video_url (str): The URL of the YouTube video.

    Returns:
        str: The full transcript text.
    """
    video_id = extract_video_id(video_url)
    logger.info(f"Processing video: {video_id}")
    
    try:
        logger.info("Fetching YouTube captions...")
        transcript = get_transcript_from_api(video_id)
        logger.info("Got transcript from YouTube captions")
        return transcript
    except Exception as e:
        error_msg = f"Error: Could not get transcript. {str(e)}"
        logger.warning(error_msg)
        return error_msg


# --- Usage ---
if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    transcript = transcript_fetcher.invoke({"video_url": url})
    print("\n--- Transcript ---\n")
    print(transcript)

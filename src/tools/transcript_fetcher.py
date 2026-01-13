from langchain.tools import tool
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import re
import os


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
    Try to fetch transcript using YouTube's caption API.
    This is instant and doesn't require downloading/transcribing.
    
    Uses proxy config from environment if available for rate limit bypass.
    """
    from settings import WEBSHARE_PROXY_USERNAME, WEBSHARE_PROXY_PASSWORD
    
    try:
        # Initialize API with proxy if credentials available
        if WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD:
            from youtube_transcript_api.proxies import WebshareProxyConfig
            print(f"🔀 Using Webshare rotating proxies")
            ytt_api = YouTubeTranscriptApi(
                proxy_config=WebshareProxyConfig(
                    proxy_username=WEBSHARE_PROXY_USERNAME,
                    proxy_password=WEBSHARE_PROXY_PASSWORD,
                )
            )
        else:
            ytt_api = YouTubeTranscriptApi()
        
        # Try to get transcript (auto-generated or manual captions)
        transcript_list = ytt_api.list(video_id)
        
        # Prefer manual transcripts, fall back to auto-generated
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                # Try any available transcript
                transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        
        # Fetch and format
        fetched_transcript = transcript.fetch()
        formatter = TextFormatter()
        return formatter.format_transcript(fetched_transcript)
        
    except Exception as e:
        raise Exception(f"No captions available: {str(e)}")


def get_transcript_with_whisper(video_url: str, model_size: str = "tiny") -> str:
    """
    Fallback: Download audio and transcribe with Whisper.
    Uses 'tiny' model for speed on CPU.
    """
    import yt_dlp
    import whisper
    from settings import YOUTUBE_COOKIES_PATH
    
    output_filename = f"temp_audio_{os.getpid()}"
    
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",  # Lower quality for faster processing
            }
        ],
        "outtmpl": output_filename,
        "quiet": True,
        "no_warnings": True,
    }
    
    if YOUTUBE_COOKIES_PATH and os.path.exists(YOUTUBE_COOKIES_PATH):
        ydl_opts["cookiefile"] = YOUTUBE_COOKIES_PATH
        print(f"🍪 Using cookies from: {YOUTUBE_COOKIES_PATH}")

    try:
        print(f"⬇️ Downloading audio (Whisper fallback)...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        print(f"🤖 Loading Whisper model ('{model_size}')...")
        model = whisper.load_model(model_size)

        print("📝 Transcribing audio...")
        result = model.transcribe(f"{output_filename}.mp3")
        return result["text"]

    finally:
        if os.path.exists(f"{output_filename}.mp3"):
            os.remove(f"{output_filename}.mp3")
            print("🧹 Cleanup complete.")


@tool
def transcript_fetcher(video_url: str) -> str:
    """
    Fetches transcript for a YouTube video.
    
    Uses YouTube's caption API first (instant), falls back to 
    Whisper transcription only if captions aren't available.

    Args:
        video_url (str): The URL of the YouTube video.

    Returns:
        str: The full transcript text.
    """
    video_id = extract_video_id(video_url)
    print(f"🎬 Processing video: {video_id}")
    
    # Try 1: YouTube Caption API (instant)
    try:
        print("📋 Fetching YouTube captions...")
        transcript = get_transcript_from_api(video_id)
        print("✅ Got transcript from YouTube captions!")
        return transcript
    except Exception as e:
        print(f"⚠️ Captions not available: {e}")
    
    # Try 2: Whisper fallback (slow but works for any video)
    try:
        print("🔄 Falling back to Whisper transcription...")
        transcript = get_transcript_with_whisper(video_url, model_size="tiny")
        print("✅ Got transcript from Whisper!")
        return transcript
    except Exception as e:
        return f"Error: Could not get transcript. {str(e)}"


# --- Usage ---
if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    transcript = transcript_fetcher.invoke({"video_url": url})
    print("\n--- Transcript ---\n")
    print(transcript)

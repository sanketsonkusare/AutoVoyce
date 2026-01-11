from langchain.tools import tool
import yt_dlp
import whisper
import os
from settings import YOUTUBE_COOKIES_PATH


@tool
def transcript_fetcher(video_url, model_size="base"):
    """
    Downloads audio from YouTube and transcribes it using OpenAI Whisper.

    Args:
        video_url (str): The URL of the YouTube video.
        model_size (str): Whisper model size ('tiny', 'base', 'small', 'medium', 'large').
                          'base' is a good balance of speed and accuracy.

    Returns:
        str: The full transcribed text.
    """

    # 1. Define temporary filename for the audio
    # We use a fixed name here to simplify cleanup, but in production
    # you might want to use unique IDs (e.g., uuid).
    output_filename = "temp_audio"

    # 2. Configure yt-dlp to download ONLY audio
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": output_filename,  # This will save as temp_audio.mp3
        "quiet": True,
        "no_warnings": True,
    }
    
    # Add cookies for YouTube authentication (bypasses bot detection)
    if YOUTUBE_COOKIES_PATH and os.path.exists(YOUTUBE_COOKIES_PATH):
        ydl_opts["cookiefile"] = YOUTUBE_COOKIES_PATH
        print(f"🍪 Using cookies from: {YOUTUBE_COOKIES_PATH}")

    try:
        print(f"⬇️  Downloading audio from: {video_url}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # 3. Load the Whisper model
        # The model loads into RAM (and GPU if available/configured)
        print(f"🤖 Loading Whisper model ('{model_size}')...")
        model = whisper.load_model(model_size)

        # 4. Transcribe the audio
        # Note: 'temp_audio.mp3' is the filename created by FFmpeg postprocessor
        print("📝 Transcribing audio (this may take a moment)...")
        result = model.transcribe(f"{output_filename}.mp3")

        return result["text"]

    except Exception as e:
        return f"Error: {str(e)}"

    finally:
        # 5. Cleanup: Remove the temporary audio file
        if os.path.exists(f"{output_filename}.mp3"):
            os.remove(f"{output_filename}.mp3")
            print("🧹 Cleanup complete.")


# --- Usage ---
if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Example URL
    transcript = transcript_fetcher.invoke({"video_url": url})

    print("\n--- Transcript ---\n")
    print(transcript)

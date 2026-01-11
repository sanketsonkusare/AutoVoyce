from langchain.tools import tool
from youtube_transcript_api import YouTubeTranscriptApi

@tool
def transcript_fetcher(video_id: str) -> str:
    """This tool fetches the transcript of a YouTube video given its video ID."""
    ytt_api = YouTubeTranscriptApi()
    return ytt_api.fetch(video_id)  

if __name__ == "__main__":
    print(transcript_fetcher.invoke("R1LE5xfasmw"))
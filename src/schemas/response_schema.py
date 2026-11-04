from typing import TypedDict, Optional

from src.tools.transcript_fetcher import Segment


class VideoInfo(TypedDict):
    id: str
    title: str
    channel: str


class VideoTranscript(TypedDict):
    video_id: str
    title: str
    channel: str
    segments: list[Segment]


class ResponseSchema(TypedDict, total=False):
    videos: list[VideoInfo]  # Videos the user selected, with titles from the search
    transcripts: list[VideoTranscript]  # One entry per video whose transcript was fetched
    namespace: str  # Session-specific Pinecone namespace
    query_response: Optional[str]  # Upload confirmation/error message
    session_id: str  # Session ID for event emission

"""Split one video's transcript into chunks for the vector index."""

from typing import TypedDict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.tools.transcript_fetcher import Segment


class Chunk(TypedDict):
    """Text for one Pinecone record. start is in seconds, None when unknown."""
    text: str
    start: float | None


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _join(segments: list[Segment]) -> str:
    return " ".join(seg["text"] for seg in segments)


def chunk_segments(segments: list[Segment], target_chars: int = 1000) -> list[Chunk]:
    """
    Group a video's segments into chunks of about target_chars characters.

    Timed segments (captions) are grouped in order; each chunk starts with the
    last segment of the previous one (one-segment overlap) and takes the start
    time of its first segment. Untimed text (Gemini) is split with a text
    splitter and has no start time.
    """
    segments = [
        {"text": _normalise(seg["text"]), "start": seg.get("start")}
        for seg in segments
    ]
    segments = [seg for seg in segments if seg["text"]]
    if not segments:
        return []

    if all(seg["start"] is None for seg in segments):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=target_chars,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return [{"text": text, "start": None} for text in splitter.split_text(_join(segments))]

    chunks: list[Chunk] = []
    current: list[Segment] = []

    def emit(group: list[Segment]) -> None:
        start = next((seg["start"] for seg in group if seg["start"] is not None), None)
        chunks.append({"text": _join(group), "start": start})

    for seg in segments:
        if current and len(_join(current + [seg])) > target_chars:
            emit(current)
            last = current[-1]
            current = [last] if len(_join([last, seg])) <= target_chars else []
        current.append(seg)
    if current:
        emit(current)
    return chunks

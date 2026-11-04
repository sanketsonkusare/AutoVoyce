"""Find the transcript passages that best answer a question."""

from dataclasses import asdict, dataclass
import logging

from pinecone import Pinecone

from settings import PINECONE_API_KEY, PINECONE_HOST_URL, RERANK_MODEL

logger = logging.getLogger("autovoyce.retrieval")

SEARCH_TOP_K = 20  # candidates from the vector search
PASSAGE_COUNT = 6  # passages given to the model
FIELDS = ["chunk_text", "video_id", "title", "channel", "start_seconds"]

_index = None


@dataclass
class Passage:
    n: int
    video_id: str
    title: str
    channel: str
    start_seconds: int | None
    text: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


def get_index():
    """Lazily create the Pinecone index client."""
    global _index
    if _index is None:
        if not PINECONE_API_KEY or not PINECONE_HOST_URL:
            raise ValueError("PINECONE_API_KEY and PINECONE_HOST_URL must be set")
        _index = Pinecone(api_key=PINECONE_API_KEY).Index(host=PINECONE_HOST_URL)
    return _index


def video_url(video_id: str, start_seconds: int | None) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    return f"{url}&t={start_seconds}s" if start_seconds is not None else url


def build_search_text(question: str, previous_question: str | None) -> str:
    """Search with the previous question too, so follow-ups keep their topic."""
    return f"{previous_question}\n{question}" if previous_question else question


def _search(namespace: str, search_text: str, rerank: dict | None) -> list[dict]:
    results = get_index().search(
        namespace=namespace,
        query={"inputs": {"text": search_text}, "top_k": SEARCH_TOP_K},
        fields=FIELDS,
        rerank=rerank,
    )
    return results.get("result", {}).get("hits", [])


def search_passages(
    namespace: str, question: str, previous_question: str | None = None
) -> list[Passage]:
    """
    Search the session's chunks and return up to PASSAGE_COUNT numbered passages.

    With RERANK_MODEL set, the top SEARCH_TOP_K hits are reranked against the
    current question. If reranking fails (quota, outage), the search runs again
    without it. Other search errors propagate.
    """
    search_text = build_search_text(question, previous_question)
    hits = None
    if RERANK_MODEL:
        rerank = {
            "model": RERANK_MODEL,
            "rank_fields": ["chunk_text"],
            "top_n": PASSAGE_COUNT,
            "query": question,
        }
        try:
            hits = _search(namespace, search_text, rerank)
        except Exception as e:
            logger.warning(f"Rerank search failed, using plain search: {e}")
    if hits is None:
        hits = _search(namespace, search_text, None)

    passages: list[Passage] = []
    for hit in hits:
        fields = hit.get("fields", {})
        text = fields.get("chunk_text") or ""
        if not text:
            continue
        video_id = fields.get("video_id") or ""
        start = fields.get("start_seconds")
        start_seconds = int(start) if isinstance(start, (int, float)) and start >= 0 else None
        passages.append(Passage(
            n=len(passages) + 1,
            video_id=video_id,
            title=fields.get("title") or "",
            channel=fields.get("channel") or "",
            start_seconds=start_seconds,
            text=text,
            url=video_url(video_id, start_seconds),
        ))
        if len(passages) == PASSAGE_COUNT:
            break
    return passages

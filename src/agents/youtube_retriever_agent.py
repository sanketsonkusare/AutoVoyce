from src.tools.youtube_search import youtube_search_with_metadata
from settings import SEARCH_LIMIT


def retriever_agent_with_metadata(query: str) -> list[dict]:
    """
    Searches YouTube and returns video metadata for user selection.
    Returns list of video dictionaries with id, title, channel, thumbnail, etc.
    """
    print(f"Searching for videos with query: '{query}'...")

    videos = youtube_search_with_metadata(query)

    # Limit to SEARCH_LIMIT
    limited_videos = videos[:SEARCH_LIMIT]

    print(f"Found {len(limited_videos)} videos")
    return limited_videos


if __name__ == "__main__":
    print(retriever_agent_with_metadata("What are some of the best Avengers movies?"))

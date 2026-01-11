from serpapi.google_search import GoogleSearch
from langchain.tools import tool
from settings import SERP_API_KEY
from typing import List, Dict, Any
import re


@tool
def youtube_query(query: str) -> list[str]:
    """This tool searches YouTube for videos related to the given
    query and returns the links of the videos in list format"""

    params = {
        "engine": "youtube",
        "search_query": query,
        "api_key": SERP_API_KEY,
        "gl": "in",
        "hl": "en",
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    video_results = results.get("video_results", [])
    links = [video["link"] for video in video_results if "link" in video]
    return links


def youtube_search_with_metadata(query: str) -> List[Dict[str, Any]]:
    """
    Searches YouTube and returns video metadata including title, channel, thumbnail, etc.
    Returns a list of dictionaries with video information.
    """
    if not SERP_API_KEY:
        print("❌ SERP_API_KEY is not set")
        raise ValueError("SERP_API_KEY environment variable is not set")

    params = {
        "engine": "youtube",
        "search_query": query,
        "api_key": SERP_API_KEY,
        "gl": "in",
        "hl": "en",
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        # Debug: Print what we got from API
        print(f"🔍 SerpAPI response keys: {list(results.keys())}")

        # Check for errors
        if "error" in results:
            print(f"❌ SerpAPI Error: {results.get('error')}")
            return []

        # Try different possible keys for video results
        video_results = results.get("video_results", [])
        if not video_results:
            video_results = results.get("videos", [])
        if not video_results:
            video_results = results.get("organic_results", [])

        print(f"📹 Found {len(video_results)} video results from API")

        videos = []
        for i, video in enumerate(video_results):
            if "link" not in video:
                print(f"⚠️ Video {i} has no link field: {list(video.keys())}")
                continue

            # Extract video ID from link
            link = video.get("link", "")
            video_id_match = re.search(r"v=([a-zA-Z0-9_-]+)", link)
            video_id = video_id_match.group(1) if video_id_match else None

            if not video_id:
                print(f"⚠️ Could not extract video ID from link: {link}")
                continue

            # Handle channel field (can be dict or string)
            channel_name = "Unknown Channel"
            channel_data = video.get("channel")
            if isinstance(channel_data, dict):
                channel_name = channel_data.get("name", "Unknown Channel")
            elif isinstance(channel_data, str):
                channel_name = channel_data

            video_info = {
                "id": video_id,
                "title": video.get("title", "Unknown Title"),
                "channel": channel_name,
                "link": link,
                "thumbnail": video.get("thumbnail", video.get("thumbnail_url", "")),
                "duration": video.get("length", video.get("duration", "N/A")),
                "views": video.get("views", video.get("view_count", "N/A")),
            }
            videos.append(video_info)
            print(f"✅ Added video: {video_info['title'][:50]}...")

        print(f"📊 Total videos processed: {len(videos)}")
        return videos

    except Exception as e:
        print(f"❌ Error in youtube_search_with_metadata: {str(e)}")
        import traceback

        traceback.print_exc()
        return []


if __name__ == "__main__":
    print(youtube_query("who is the best avenger"))
    print("\n---\n")
    print(youtube_search_with_metadata("who is the best avenger"))

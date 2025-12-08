from serpapi import GoogleSearch
from langchain.tools import tool
from settings import SERP_API_KEY

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
    links = [video['link'] for video in video_results if 'link' in video]
    return links


if __name__ == "__main__":
    print(youtube_query("who is the best avenger"))
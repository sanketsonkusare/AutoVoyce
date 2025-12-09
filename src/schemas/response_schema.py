from typing import TypedDict

class ResponseSchema(TypedDict):
    user_query: str
    video_ids: list[str]
    transcript: str

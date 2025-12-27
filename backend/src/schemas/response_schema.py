from typing import TypedDict, Optional

class ResponseSchema(TypedDict, total=False):
    user_query: str
    video_ids: list[str]
    transcript: str
    namespace: str  # Session-specific Pinecone namespace
    query_response: Optional[str]  # Upload confirmation/error message

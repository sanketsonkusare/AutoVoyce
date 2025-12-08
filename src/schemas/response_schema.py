from typing import TypedDict, Literal

class ResponseSchema(TypedDict):
    user_query: str
    query_response: str
    
from pinecone import Pinecone
from settings import PINECONE_API_KEY, PINECONE_HOST_URL
from langchain.tools import tool
from pydantic import Field
from src.utils import session_manager

# Lazy initialization - only create when needed
_pc = None
_index = None

def get_index():
    """Lazily initializes and returns the Pinecone index."""
    global _pc, _index
    if _index is None:
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY environment variable is not set")
        if not PINECONE_HOST_URL:
            raise ValueError("PINECONE_HOST_URL environment variable is not set")
        _pc = Pinecone(api_key=PINECONE_API_KEY)
        _index = _pc.Index(host=PINECONE_HOST_URL)
    return _index


@tool
def query_tool(query: str = Field(description="The search query to find relevant context from the vector database."), namespace: str = Field(description="The namespace to search in.")) -> str:
    """
    Searches the Pinecone vector index for relevant context based on the query.
    Returns a comma-separated string of relevant text chunks.
    Uses the current namespace from session context.
    """    
    print(f"🔍 query_tool searching in namespace: {namespace}")
    
    index = get_index()
    results = index.search(
        namespace=namespace, 
        query={
            "inputs": {"text": query}, 
            "top_k": 5
        },
        fields=["chunk_text"]
    )
    hits = results.get("result", {}).get("hits", [])
    chunk_texts = [hit["fields"]["chunk_text"] for hit in hits if "fields" in hit and "chunk_text" in hit["fields"]]
    return ", ".join(set(chunk_texts))

if __name__ == "__main__":
    results = query_tool(query="Which iphone is best for students?", namespace="session_716979f0")

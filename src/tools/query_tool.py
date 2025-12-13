from pinecone import Pinecone
from settings import PINECONE_API_KEY, PINECONE_HOST_URL,NAMESPACE
from langchain.tools import tool
from pydantic import Field

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST_URL)


@tool
def query_tool(query: str = Field(description="The search query to find relevant context from the vector database.")) -> str:
    """
    Searches the Pinecone vector index for relevant context based on the query.
    Returns a comma-separated string of relevant text chunks.
    """
    results = index.search(
        namespace=NAMESPACE, 
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
    results = query_tool(query="Which iphone is best for students?")

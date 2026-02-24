from settings import PINECONE_API_KEY, PINECONE_INDEX_NAME, PINECONE_HOST_URL
from pinecone import Pinecone
from src.utils.event_emitter import event_emitter
import uuid
import logging

logger = logging.getLogger("autovoyce.vector_index")


class PineconeVectorIndex:
    """
    Wrapper around Pinecone index using integrated inference.
    Embeddings are generated server-side — no local model needed.
    """

    def __init__(self, session_id: str = ""):
        self.__index_name = PINECONE_INDEX_NAME
        self.__pc = Pinecone(api_key=PINECONE_API_KEY)
        self.__index = self.__pc.Index(host=PINECONE_HOST_URL)
        self.__session_id = session_id

    def upsert_chunks(self, chunks: list[str], namespace: str, batch_size: int = 96):
        """
        Upsert text chunks to Pinecone using integrated inference.
        Pinecone auto-embeds the chunk_text field server-side.
        """
        if not chunks:
            return

        records = [
            {
                "_id": str(uuid.uuid4()),
                "chunk_text": chunk,
                "chunk_id": i,
                "source": "uploaded_document",
            }
            for i, chunk in enumerate(chunks)
        ]

        total_uploaded = 0
        for batch_start in range(0, len(records), batch_size):
            batch = records[batch_start : batch_start + batch_size]
            self.__index.upsert_records(namespace, batch)
            total_uploaded += len(batch)

        msg = f"Uploaded {total_uploaded} chunks to Pinecone index '{self.__index_name}' in namespace '{namespace}'"
        logger.info(msg)
        print(msg)

        if self.__session_id:
            event_emitter.emit(self.__session_id, "chunks_uploaded", msg, {
                "chunk_count": total_uploaded,
                "namespace": namespace,
            })

    def search(self, query: str, namespace: str, top_k: int = 5) -> list[str]:
        """
        Hybrid search using Pinecone integrated inference (semantic + lexical).
        Combines dense embeddings (from inputs.text) with a BM25-style sparse vector.
        Requires index with metric='dotproduct' to support both dense and sparse vectors.
        """
        from collections import Counter

        # Generate sparse vector for lexical/keyword matching (BM25-style term frequencies)
        words = query.lower().split()
        word_counts = Counter(words)
        sparse_vector = {
            "indices": list(range(len(word_counts))),
            "values": [float(count) for count in word_counts.values()],
        }

        results = self.__index.search(
            namespace=namespace,
            query={
                "inputs": {"text": query},        # Dense embedding (semantic)
                "sparse_vector": sparse_vector,    # Lexical/keyword boost
                "top_k": top_k,
            },
            fields=["chunk_text"],
        )
        hits = results.get("result", {}).get("hits", [])
        return [
            hit["fields"]["chunk_text"]
            for hit in hits
            if "fields" in hit and "chunk_text" in hit["fields"]
        ]

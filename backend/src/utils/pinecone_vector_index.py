from src.utils.base import VectorIndexStrategy
from settings import PINECONE_API_KEY, PINECONE_INDEX_NAME
from pinecone import Pinecone
from src.utils.event_emitter import event_emitter

class PineconeVectorIndex(VectorIndexStrategy):
    def  __init__ (self, embeddings, session_id: str = ""):
        self.__collection_name = PINECONE_INDEX_NAME
        self.__api_key = Pinecone(api_key=PINECONE_API_KEY)
        self.__embeddings = embeddings
        self.__collection = False
        self.__session_id = session_id

    def create_or_load_vector_index(self, markdown_text: str, chunker=None, namespace: str = None):
        # Note: We removed the self.__collection check because we want to allow multiple uploads to different namespaces
        
        index = self.__api_key.Index(self.__collection_name)
        # Use provided chunker callable if supplied; it may return Documents or strings
        if chunker is not None:
            chunk_outputs = chunker(markdown_text)
            if chunk_outputs and hasattr(chunk_outputs[0], "page_content"):
                chunk_texts = [c.page_content for c in chunk_outputs]
            else:
                chunk_texts = list(chunk_outputs)
        else:
            # Fallback: no chunker provided; treat whole markdown as a single chunk
            chunk_texts = [markdown_text] if markdown_text else []
        if not chunk_texts:
            return self

        # Embed documents using langchain's HuggingFaceEmbeddings
        vectors = self.__embeddings.embed_documents(chunk_texts)
        pinecone_vectors = []
        import uuid
        for i, (values, chunk_text) in enumerate(zip(vectors, chunk_texts)):
            # Use UUID to ensure unique IDs across multiple uploads
            chunk_id = str(uuid.uuid4())
            pinecone_vectors.append({
                "id": chunk_id,
                "values": values,
                "metadata": {
                    "chunk_text": chunk_text,
                    "chunk_id": i,
                    "source": "uploaded_document"
                }
            })

        # Upsert to Pinecone with namespace
        index.upsert(vectors=pinecone_vectors, namespace=namespace)
        print(f"Uploaded {len(pinecone_vectors)} chunks to Pinecone index '{self.__collection_name}' in namespace '{namespace}'")
        if self.__session_id:
            event_emitter.emit(self.__session_id, "chunks_uploaded", f"Uploaded {len(pinecone_vectors)} chunks to Pinecone", {
                "chunk_count": len(pinecone_vectors),
                "namespace": namespace
            })
        self.__collection = True
        return self
    
    def semantic_search(self, embeded_query: list[float], namespace: str = None) -> str:
        if namespace is None:
            raise ValueError("Namespace is required for semantic search to ensure data isolation.")
            
        index = self.__api_key.Index(self.__collection_name)
        response = index.query(
            vector=embeded_query,
            top_k=20,
            include_metadata=True,
            score_threshold=0.7,
            namespace=namespace
        )
        if response.get("matches"):
            context = response["matches"][0]["metadata"].get("chunk_text", "")
            return context or "No relevant context found for the question."
        else:
            return "No relevant context found for the question."

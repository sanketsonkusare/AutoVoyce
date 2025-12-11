from datetime import datetime
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from src.utils.pinecone_vector_index import PineconeVectorIndex
from src.schemas.response_schema import ResponseSchema

def pinecone_uploader(state: ResponseSchema) -> dict:
    print("Starting Pinecone upload process...")
    transcript = state.get("transcript", "")
    if not transcript:
        print("No transcript to upload.")
        return {"query_response": "No transcript found to upload."}

    try:
        # Initialize Embeddings
        print("Initializing Embedding Model (sentence-transformers/all-MiniLM-L6-v2)...")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        # Initialize Vector Index Wrapper
        vector_index = PineconeVectorIndex(embeddings)
        
        # Define Chunker
        chunker = SemanticChunker(
            embeddings,
            breakpoint_threshold_type="percentile"  # 95th percentile similarity threshold
        )
        
        def chunker_wrapper(text: str):
            chunks = chunker.split_text(transcript)
            return chunks
        
        # Upload
        # We use a default namespace or generate one. Let's use "youtube-transcripts" or derived from query.
        namespace = "youtube_transcripts"
        print(f"Uploading transcript to Pinecone (Namespace: {namespace})...")
        
        vector_index.create_or_load_vector_index(
            markdown_text=transcript,
            chunker=chunker_wrapper,
            namespace=namespace
        )
        
        success_msg = f"Transcript successfully uploaded to Pinecone namespace '{namespace}'."
        print(success_msg)
        return {"query_response": success_msg}
        
    except Exception as e:
        error_msg = f"Error uploading to Pinecone: {str(e)}"
        print(error_msg)
        # Import traceback to print full stack trace for debugging
        import traceback
        traceback.print_exc()
        return {"query_response": error_msg}

if __name__ == "__main__":
    # Test execution
    mock_state = {"user_query": "test", "video_ids": [], "transcript": "This is a test transcript for Pinecone upload verification.\n" * 50, "query_response": ""}
    print(pinecone_uploader(mock_state))
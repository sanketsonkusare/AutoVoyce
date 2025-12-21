from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from src.utils.pinecone_vector_index import PineconeVectorIndex
from langchain.tools import tool

@tool
def upload_transcript_to_pinecone(transcript: str, namespace: str = "youtube_transcripts") -> str:
    """
    Uploads a YouTube transcript to the Pinecone vector database.
    Useful when you need to store transcript text for later retrieval or Q&A.
    
    Args:
        transcript: The transcript text to upload
        namespace: The Pinecone namespace to use for isolation (default: "youtube_transcripts")
    """
    print("Starting Pinecone upload process...")
    if not transcript:
        print("No transcript to upload.")
        return "No transcript found to upload."

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
        
        # Upload to specified namespace
        print(f"Uploading transcript to Pinecone (Namespace: {namespace})...")
        
        vector_index.create_or_load_vector_index(
            markdown_text=transcript,
            chunker=chunker_wrapper,
            namespace=namespace
        )
        
        success_msg = f"Transcript successfully uploaded to Pinecone namespace '{namespace}'."
        print(success_msg)
        return success_msg
        
    except Exception as e:
        error_msg = f"Error uploading to Pinecone: {str(e)}"
        print(error_msg)
        # Import traceback to print full stack trace for debugging
        import traceback
        traceback.print_exc()
        return error_msg

if __name__ == "__main__":
    # Test execution
    mock_transcript = "This is a test transcript for Pinecone upload verification.\n" * 50
    print(upload_transcript_to_pinecone.invoke({"transcript": mock_transcript}))
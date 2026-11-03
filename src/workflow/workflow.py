from langgraph.graph import StateGraph, START, END
from src.agents.youtube_transcript_agent import transcript_agent
from src.agents.pinecone_uploader_agent import uploader_agent
from src.schemas.response_schema import ResponseSchema

# Processing workflow (transcript -> uploader) for videos the user already selected
processing_graph = StateGraph(ResponseSchema)

processing_graph.add_node("transcript", transcript_agent)
processing_graph.add_node("uploader", uploader_agent)

processing_graph.add_edge(START, "transcript")
processing_graph.add_edge("transcript", "uploader")
processing_graph.add_edge("uploader", END)

processing_workflow = processing_graph.compile()

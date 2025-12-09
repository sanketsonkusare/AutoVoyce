from langgraph.graph import StateGraph, START, END
from src.agents.youtube_retriever_agent import retriever_agent
from src.agents.youtube_transcript_agent import transcript_agent
from src.schemas.response_schema import ResponseSchema

# Define Graph
graph = StateGraph(ResponseSchema)

graph.add_node("retriever", retriever_agent)
graph.add_node("transcript", transcript_agent)

graph.add_edge(START, "retriever")
graph.add_edge("retriever", "transcript")
graph.add_edge("transcript", END)

workflow = graph.compile()

if __name__ == "__main__":
    initial_state = {"user_query": "best value for money iphones", "video_ids": [], "transcript": ""}
    result = workflow.invoke(initial_state)
    
    print("\n\nFINAL WORKFLOW RESULT")
    print(f"User Query: {result['user_query']}")
    print(f"Video IDs: {result['video_ids']}")
    print(f"Transcripts:\n{result['transcript']}")

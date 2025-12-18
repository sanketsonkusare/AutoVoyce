from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.workflow.workflow import workflow
from src.agents.pinecone_query_agent import query_agent

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


class QueryRequest(BaseModel):
    user_query: str


@app.get("/")
def read_root():
    return {"message": "AutoVoyce API is running"}


@app.post("/upload")
def run_workflow(request: QueryRequest):
    """
    Invokes the main AutoVoyce workflow with the provided user request.
    """
    try:
        initial_state = {
            "user_query": request.user_query,
            "video_ids": [],
            "transcript": "",
        }
        result = workflow.invoke(initial_state)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
def query_endpoint(request: QueryRequest):
    """
    Invokes the Pinecone Query Agent to answer questions based on the knowledge base.
    """
    try:
        result = query_agent(request.user_query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

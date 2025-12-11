import yaml
# from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from settings import GROQ_API_KEY
from pathlib import Path


PROMPTS_PATH = Path(__file__).resolve().parent.parent / "utils" / "promps.yml"
with open(PROMPTS_PATH, "r") as f:
    PROMPTS = yaml.safe_load(f)

def create_agent_with_tools(agent_name: str, tools: list):
    """
    Creates a LangChain agent with the specified name and tools.
    The system prompt is fetched from src/utils/promps.yml using agent_name + '_prompt'.
    """
    prompt_key = f"{agent_name}_prompt"
    system_prompt = PROMPTS.get(prompt_key)
    
    if not system_prompt:
        raise ValueError(f"Prompt for '{agent_name}' not found in {PROMPTS_PATH}. Key expected: {prompt_key}")

    model = ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
    
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )
    
    return agent

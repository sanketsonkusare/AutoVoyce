import yaml
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from settings import GOOGLE_API_KEY
from pathlib import Path


PROMPTS_PATH = Path(__file__).resolve().parent.parent / "utils" / "promps.yml"
with open(PROMPTS_PATH, "r") as f:
    PROMPTS = yaml.safe_load(f)

def create_agent_with_tools(agent_name: str, tools: list, verbose: bool = True):
    """
    Creates a LangGraph ReAct agent with the specified name and tools.
    The system prompt is fetched from src/utils/promps.yml using agent_name + '_prompt'.
    
    Args:
        agent_name: Name of the agent (used to fetch prompt)
        tools: List of tools to provide to the agent
        verbose: Enable verbose logging (default: True)
    """
    prompt_key = f"{agent_name}_prompt"
    system_prompt_text = PROMPTS.get(prompt_key)
    
    if not system_prompt_text:
        raise ValueError(f"Prompt for '{agent_name}' not found in {PROMPTS_PATH}. Key expected: {prompt_key}")

    # Ensure GOOGLE_API_KEY is set
    if not GOOGLE_API_KEY:
        # Try reloading environment in case we're in a background thread
        from dotenv import load_dotenv
        from os import getenv
        load_dotenv(".env")
        api_key = getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it in your .env file.")
    else:
        api_key = GOOGLE_API_KEY

    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=api_key, verbose=verbose)
    
    # Wrap prompt in SystemMessage
    system_prompt = SystemMessage(content=system_prompt_text)
    
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )
    
    return agent

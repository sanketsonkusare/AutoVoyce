from dotenv import load_dotenv
from os import getenv
from pathlib import Path

load_dotenv(".env")

BASE_DIR = Path(__file__).resolve().parent.parent

GOOGLE_API_KEY=getenv("GOOGLE_API_KEY")
SERP_API_KEY=getenv("SERP_API_KEY")
SEARCH_LIMIT=int(getenv("SEARCH_LIMIT"))
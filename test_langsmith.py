"""Verify LangSmith tracing is active."""
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
print("LANGCHAIN_TRACING_V2:", os.getenv("LANGCHAIN_TRACING_V2"))
print("LANGCHAIN_PROJECT:", os.getenv("LANGCHAIN_PROJECT"))
key = os.getenv("LANGCHAIN_API_KEY", "")
print("LANGCHAIN_API_KEY:", key[:20] + "..." if key else "NOT SET")

from langsmith import Client
client = Client()
try:
    projects = list(client.list_projects())
    print(f"\nLangSmith connected. Projects: {[p.name for p in projects]}")
except Exception as e:
    print(f"\nLangSmith error: {e}")

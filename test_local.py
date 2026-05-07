"""Quick smoke test — local Ollama only, no cloud needed."""
from dotenv import load_dotenv
load_dotenv()
import litellm
litellm.set_verbose = False

r = litellm.completion(
    model="ollama/qwen25-coder-14b",
    messages=[{"role": "user", "content": "Reply with just: OK"}],
    api_base="http://localhost:11434",
    temperature=0.0,
)
print("Ollama:", r.choices[0].message.content.strip())

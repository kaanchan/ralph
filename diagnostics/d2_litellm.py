"""D2: LiteLLM -> Ollama completion.
Checks: import, env vars set, completion returns non-empty text in <30s.
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
import config  # loads .env before litellm reads env
import os

def check(label, fn):
    try:
        fn()
        print(f"  PASS  {label}")
        return True
    except Exception as e:
        print(f"  FAIL  {label}")
        print(f"        {type(e).__name__}: {e}")
        return False

def can_import_litellm():
    import litellm  # noqa: F401

def env_var_set():
    v = os.environ.get("OLLAMA_API_BASE") or os.environ.get("OLLAMA_BASE_URL") or ""
    assert v.startswith("http"), f"OLLAMA_API_BASE not set or invalid: '{v}'"

def completion_returns_text():
    import litellm
    resp = litellm.completion(
        model=config.LOCAL_MODEL,
        messages=[{"role": "user", "content": "Reply with just the word OK"}],
        api_base=config.OLLAMA_BASE_URL,
        max_tokens=5,
        timeout=30,
    )
    text = resp.choices[0].message.content.strip()
    assert text, f"empty response from model"
    print(f"          model replied: {text!r}")

if __name__ == "__main__":
    print(f"\n[D2] LiteLLM -> Ollama  (model={config.LOCAL_MODEL})")
    results = [
        check("litellm package importable", can_import_litellm),
        check("OLLAMA_API_BASE env var is set", env_var_set),
        check("completion returns text in <30s", completion_returns_text),
    ]
    ok = all(results)
    print(f"\n  {'ALL PASS' if ok else 'FAILED'}\n")
    sys.exit(0 if ok else 1)

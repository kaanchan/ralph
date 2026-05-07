"""D5: LangSmith tracing.
Checks: env vars set, API key is non-placeholder, a traced LiteLLM call
completes without error (trace appears in LangSmith automatically via
LANGCHAIN_TRACING_V2=true — we can't fetch run IDs without the SDK,
so we verify the call succeeds and print the expected trace URL).
"""
import sys, os
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
import config  # loads .env

def check(label, fn):
    try:
        fn()
        print(f"  PASS  {label}")
        return True
    except Exception as e:
        print(f"  FAIL  {label}")
        print(f"        {type(e).__name__}: {e}")
        return False

def tracing_env_set():
    v2 = os.environ.get("LANGCHAIN_TRACING_V2", "")
    assert v2.lower() == "true", f"LANGCHAIN_TRACING_V2={v2!r} (must be 'true')"

def api_key_set():
    key = os.environ.get("LANGCHAIN_API_KEY", "")
    assert key.startswith("lsv2_"), (
        f"LANGCHAIN_API_KEY looks wrong (starts with {key[:8]!r}). "
        "Get a key at https://smith.langchain.com -> Settings -> API Keys"
    )

def project_name_set():
    proj = os.environ.get("LANGCHAIN_PROJECT", "")
    assert proj, "LANGCHAIN_PROJECT is not set — traces will land in 'default'"
    print(f"          project: {proj!r}")

def traced_call_succeeds():
    import litellm
    # A tiny call — LangGraph/LangSmith auto-traces via LANGCHAIN_TRACING_V2
    resp = litellm.completion(
        model=config.LOCAL_MODEL,
        messages=[{"role": "user", "content": "say hi"}],
        api_base=config.OLLAMA_BASE_URL,
        max_tokens=3,
        timeout=30,
    )
    text = resp.choices[0].message.content.strip()
    proj = os.environ.get("LANGCHAIN_PROJECT", "default")
    print(f"          model replied: {text!r}")
    print(f"          check traces at https://smith.langchain.com -> project '{proj}'")

if __name__ == "__main__":
    print(f"\n[D5] LangSmith tracing")
    results = [
        check("LANGCHAIN_TRACING_V2=true", tracing_env_set),
        check("LANGCHAIN_API_KEY set (lsv2_ prefix)", api_key_set),
        check("LANGCHAIN_PROJECT set", project_name_set),
        check("traced LiteLLM call completes", traced_call_succeeds),
    ]
    ok = all(results)
    print(f"\n  {'ALL PASS' if ok else 'FAILED'}\n")
    sys.exit(0 if ok else 1)

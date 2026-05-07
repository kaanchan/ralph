"""D1: Ollama server + model availability.
Checks: server reachable, target model listed, 1-token generation succeeds.
"""
import sys, json, urllib.request, urllib.error
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
import config  # loads .env

BASE = config.OLLAMA_BASE_URL
MODEL = config.LOCAL_MODEL.removeprefix("ollama/")

def check(label, fn):
    try:
        fn()
        print(f"  PASS  {label}")
        return True
    except Exception as e:
        print(f"  FAIL  {label}")
        print(f"        {e}")
        return False

def server_reachable():
    urllib.request.urlopen(f"{BASE}/", timeout=3)

def model_listed():
    with urllib.request.urlopen(f"{BASE}/api/tags", timeout=5) as r:
        tags = json.loads(r.read())
    names = [m["name"].split(":")[0] for m in tags.get("models", [])]
    assert any(MODEL in n for n in names), f"{MODEL} not in {names}"

def one_token_generate():
    payload = json.dumps({
        "model": MODEL, "prompt": "hi", "stream": False,
        "options": {"num_predict": 1}
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/api/generate", data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    assert body.get("response") is not None, f"empty response: {body}"

if __name__ == "__main__":
    print(f"\n[D1] Ollama  ({BASE}  model={MODEL})")
    results = [
        check("server reachable at localhost:11434", server_reachable),
        check(f"model '{MODEL}' is listed in /api/tags", model_listed),
        check("1-token generation completes in <30s", one_token_generate),
    ]
    ok = all(results)
    print(f"\n  {'ALL PASS' if ok else 'FAILED'}\n")
    sys.exit(0 if ok else 1)

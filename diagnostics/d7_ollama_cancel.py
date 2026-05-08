import json
import time
import urllib.request
import threading
import sys

OLLAMA_API_BASE = "http://localhost:11434"
MODEL = "qwen25-coder-14b" # From config

def check_ps():
    req = urllib.request.Request(f"{OLLAMA_API_BASE}/api/ps")
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode("utf-8"))
            models = data.get("models", [])
            for m in models:
                print(f"[PS] {m['name']} - {m.get('size', 0)} bytes, details: {m.get('details', {})}")
            return len(models) > 0
    except Exception as e:
        print(f"[PS] Error: {e}")
        return False

def long_generation():
    print(f"\n--- Starting long generation ---")
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "Write a very long and detailed essay about the history of artificial intelligence, at least 2000 words. Think step by step and be extremely verbose."}
        ],
        "stream": True
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_API_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            tokens_read = 0
            for raw in iter(r.readline, b""):
                if not raw.strip(): continue
                chunk = json.loads(raw.decode("utf-8"))
                token = chunk.get("message", {}).get("content", "")
                if token:
                    tokens_read += 1
                    sys.stdout.write(token)
                    sys.stdout.flush()
                if tokens_read >= 20:
                    print(f"\n\n[Client] Read 20 tokens. Simulating timeout by abruptly closing socket.")
                    break # Breaking out of 'with' block closes socket
    except Exception as e:
        print(f"\n[Client] Generation exception: {e}")
    print(f"[Client] Socket closed. Elapsed: {time.time() - start:.2f}s")

def test_cancellation():
    print("Checking initial state...")
    check_ps()
    
    long_generation()
    
    print("\n--- Testing responsiveness immediately after disconnect ---")
    # Test if Ollama is blocked by sending a short prompt
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "Say 'hello' in one word."}],
        "stream": False
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_API_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    start = time.time()
    print("Sending short request...")
    # Also poll ps while waiting
    def poll_ps():
        for _ in range(5):
            check_ps()
            time.sleep(2)
    t = threading.Thread(target=poll_ps)
    t.start()
    
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            response = json.loads(r.read().decode("utf-8"))
            print(f"\n[Short Request] Success! Took {time.time() - start:.2f}s. Response: {response.get('message', {}).get('content')}")
    except Exception as e:
        print(f"\n[Short Request] Failed! Took {time.time() - start:.2f}s. Error: {e}")
    
    t.join()

if __name__ == "__main__":
    test_cancellation()

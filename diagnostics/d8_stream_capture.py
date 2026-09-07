"""D8 — Stream-capture diagnostic (docs/Claude_Handoff.md Sec 8, Step 1).

Unresolved question 7b in the handoff doc: a 654-char plan finishes
test/solution generation in ~5s, but a 1108-char plan blows up to 90s+ --
a ~2x prompt increase causing a ~20x time increase. This script isolates
plan LENGTH as the only variable, builds prompts from the REAL templates in
prompts/, and captures every raw streaming chunk from Ollama so we can see
whether the model enters a reasoning/thinking preamble before emitting code.

It also incidentally validates the fix already applied in executor.py/
prompts/test_solution.txt (the plan is no longer included in the test
prompt at all -- see docs/Claude_Handoff.md Sec 8 Step 2): if that fix
holds, test_solution.py generation should stay fast regardless of plan
length, since the plan is not part of that prompt in current code.

Follows the gpu-guard skill: a 1-token PRECHECK (short timeout) before any
real call, a capped num_ctx (8192) to avoid the 16GB-VRAM CPU-spill wedge,
and a first-token LIVENESS DEADLINE that aborts+unloads instead of hanging.

Usage:
    python diagnostics/d8_stream_capture.py
"""
import json
import sys
import time
import threading
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
PROMPTS_DIR = ROOT / "prompts"
OUT_DIR = HERE / "d8_output"
OUT_DIR.mkdir(exist_ok=True)

OLLAMA_API_BASE = "http://localhost:11434"
MODEL = "qwen25-coder-14b"
NUM_CTX = 8192          # VRAM-safe cap (gpu-guard) -- keeps the 9GB q4 model on-GPU
PING_TIMEOUT = 15       # precheck: fail fast if the runner is sick
LIVENESS_DEADLINE = 150 # abort+unload if no first token arrives in this long

TASK = (
    "Write a function is_palindrome(s: str) -> bool that returns True if s "
    "reads the same forwards and backwards, ignoring case and non-alphanumeric "
    "characters."
)

# Same content/structure, deliberately sized to bracket the handoff doc's
# known-fast (654 char) / known-slow (1108 char) plan lengths.
SHORT_PLAN = (
    "Language: Python 3.11.\n"
    "File: solution.py -- one function is_palindrome(s: str) -> bool.\n"
    "Strip non-alphanumeric chars, lowercase, compare to its reverse.\n"
    "Tests: test_solution.py -- pytest functions, import is_palindrome from solution.\n"
    "Success: handles empty string, punctuation, mixed case, single char."
)

LONG_PLAN = SHORT_PLAN + (
    "\n\nAdditional detail: is_palindrome must run in O(n) time and O(1) extra "
    "space beyond the cleaned string; use two pointers from each end rather "
    "than slicing/reversing the whole string, so it also demonstrates the "
    "algorithmic technique instead of relying on Python's slice reversal. "
    "Consider Unicode letters via str.isalnum() rather than a fixed ASCII "
    "allowlist so accented characters are still compared correctly. Document "
    "the function with a short docstring giving one example call and its "
    "expected return value."
)


def load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def build_prompts(plan: str) -> dict:
    """Mirror executor.py's run_aider() prompt construction exactly."""
    plan_prefix = f"{plan}\n\n" if plan else ""
    sol_prompt = (
        load_prompt("solution.txt")
        .replace("{plan_prefix}", plan_prefix)
        .replace("{task}", TASK)
    )
    # test_solution.txt takes {task} only -- the plan is deliberately NOT
    # included (docs/Claude_Handoff.md Sec 8 Step 2, already applied).
    test_prompt = load_prompt("test_solution.txt").replace("{task}", TASK)
    return {"solution.py": sol_prompt, "test_solution.py": test_prompt}


def ping() -> bool:
    """gpu-guard rule 2: trivial 1-token ping under a short timeout."""
    payload = json.dumps({
        "model": MODEL,
        "prompt": "ping",
        "stream": False,
        "options": {"num_predict": 1, "num_ctx": NUM_CTX},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_API_BASE}/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=PING_TIMEOUT) as r:
            json.loads(r.read())
        return True
    except Exception as e:
        print(f"d8: PRECHECK FAILED -- {e}", file=sys.stderr)
        return False


def unload():
    try:
        payload = json.dumps({"model": MODEL, "keep_alive": 0}).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_API_BASE}/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print(f"d8: unload best-effort failed ({e})", file=sys.stderr)


def stream_capture(label: str, prompt: str) -> dict:
    """Stream a real generation call, logging every raw chunk with a
    timestamp. Returns timing/shape stats; aborts+unloads on a wedge
    (gpu-guard rule 3: first-token liveness deadline)."""
    log_path = OUT_DIR / f"{label}.jsonl"
    state = {"chunks": [], "err": None, "done": False}
    t0 = time.monotonic()

    def worker():
        try:
            payload = json.dumps({
                "model": MODEL, "prompt": prompt, "stream": True,
                "options": {"num_ctx": NUM_CTX},
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{OLLAMA_API_BASE}/api/generate", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=LIVENESS_DEADLINE) as resp:
                for raw in resp:
                    if not raw.strip():
                        continue
                    obj = json.loads(raw)
                    obj["_t"] = round(time.monotonic() - t0, 3)
                    state["chunks"].append(obj)
                    if obj.get("done"):
                        break
            state["done"] = True
        except Exception as e:
            state["err"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    while not state["chunks"] and state["err"] is None and not state["done"]:
        if time.monotonic() - t0 > LIVENESS_DEADLINE:
            print(f"d8: [{label}] LIVENESS DEADLINE ({LIVENESS_DEADLINE}s) -- "
                  f"0 tokens. Aborting + unloading.", file=sys.stderr)
            unload()
            return {"label": label, "wedged": True}
        time.sleep(0.25)

    t.join(timeout=LIVENESS_DEADLINE)

    with log_path.open("w", encoding="utf-8") as f:
        for obj in state["chunks"]:
            f.write(json.dumps(obj) + "\n")

    if state["err"] is not None:
        print(f"d8: [{label}] transport error: {state['err']}", file=sys.stderr)
        return {"label": label, "error": str(state["err"])}

    text = "".join(c.get("response", "") for c in state["chunks"])
    first_token_t = state["chunks"][0]["_t"] if state["chunks"] else None
    fence_idx = text.find("```")
    # Walk chunks to find the elapsed time at which the fence character
    # position was reached, so we know how much (if any) pre-fence text the
    # model emitted before starting the code block.
    fence_t = None
    if fence_idx != -1:
        seen = 0
        for c in state["chunks"]:
            seen += len(c.get("response", ""))
            if seen >= fence_idx:
                fence_t = c["_t"]
                break
    done_t = state["chunks"][-1]["_t"] if state["chunks"] else None

    return {
        "label": label,
        "prompt_chars": len(prompt),
        "first_token_s": first_token_t,
        "first_fence_s": fence_t,
        "done_s": done_t,
        "pre_fence_chars": fence_idx if fence_idx != -1 else len(text),
        "total_chars": len(text),
        "log_file": str(log_path),
    }


def main():
    print(f"d8: pinging {MODEL} (<= {PING_TIMEOUT}s, num_ctx={NUM_CTX})...")
    if not ping():
        print("d8: precheck failed -- ollama runner not responsive. "
              "Not proceeding (see gpu-guard skill Recovery section).", file=sys.stderr)
        sys.exit(2)
    print("d8: precheck OK.\n")

    results = []
    for plan_label, plan in [("short_plan", SHORT_PLAN), ("long_plan", LONG_PLAN)]:
        prompts = build_prompts(plan)
        for file_label, prompt in prompts.items():
            label = f"{plan_label}__{file_label.replace('.py', '')}"
            print(f"d8: streaming [{label}] prompt_chars={len(prompt)} ...")
            result = stream_capture(label, prompt)
            results.append(result)
            print(f"d8: [{label}] -> {result}\n")

    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"d8: summary written to {summary_path}")


if __name__ == "__main__":
    main()

"""D_model: Direct local model capability — no Aider, no LiteLLM.

Calls Ollama /api/chat directly to answer three questions before involving
any other layer:

  1. Can the model generate valid Python code at all?
  2. Can the model follow SEARCH/REPLACE diff format (what Aider's diff mode needs)?
  3. Can the model follow whole-file format (what Aider's whole mode needs)?
  4. How long does it take? (latency profile)
  5. Does a realistic RALPH plan prompt cause the model to stall or degrade?

Run this BEFORE D3. If these fail, Aider will never produce edits regardless
of flags or wiring — the problem is upstream.
"""
import sys, json, time, urllib.request, urllib.error
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
import config

BASE  = config.OLLAMA_BASE_URL
MODEL = config.LOCAL_MODEL.removeprefix("ollama/")

_start = time.time()
def ts(): return f"[+{time.time()-_start:5.1f}s]"
def log(msg): print(msg, flush=True)
def ok(label):    log(f"  PASS  {label}  {ts()}")
def fail(label, detail=""):
    log(f"  FAIL  {label}  {ts()}")
    for l in str(detail).splitlines(): log(f"        {l}")
    sys.exit(1)
def step(label):  log(f"\n  -- {label}  {ts()}")
def show(label, text):
    log(f"\n  [{label}]")
    for l in text.splitlines(): log(f"    {l}")
    log("")


def chat(messages, timeout=60):
    """POST to /api/chat, return (response_text, elapsed_seconds)."""
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode("utf-8"))
    elapsed = time.time() - t0
    return body["message"]["content"], elapsed


# ── 1. Ollama reachable ───────────────────────────────────────────────────────

step("Ollama reachable and model loaded")
try:
    urllib.request.urlopen(f"{BASE}/", timeout=3)
    ok(f"Ollama at {BASE}")
except Exception as e:
    fail("Ollama unreachable", e)

try:
    with urllib.request.urlopen(f"{BASE}/api/tags", timeout=5) as r:
        tags = json.loads(r.read())
    names = [m["name"].split(":")[0] for m in tags.get("models", [])]
    assert any(MODEL in n for n in names), f"{MODEL} not in {names}"
    ok(f"model '{MODEL}' listed in /api/tags")
except Exception as e:
    fail(f"model '{MODEL}' not found", e)


# ── 2. Basic code generation ──────────────────────────────────────────────────

step("Basic Python code generation (no format constraint)")
BASIC_MESSAGES = [
    {"role": "system", "content": "You are an expert Python programmer. Reply with only code, no explanation."},
    {"role": "user",   "content": "Write a Python function called add_numbers(a, b) that returns a + b. Include a docstring."},
]
try:
    reply, elapsed = chat(BASIC_MESSAGES, timeout=60)
    show("RAW MODEL RESPONSE — basic code generation", reply)
    has_def    = "def add_numbers" in reply
    has_return = "return" in reply
    if not has_def or not has_return:
        fail("basic code generation",
             f"Expected 'def add_numbers' and 'return' in response.\nGot:\n{reply}")
    ok(f"model produced valid Python function  ({elapsed:.1f}s, {len(reply)} chars)")
except Exception as e:
    fail("basic code generation", e)


# ── 3. SEARCH/REPLACE diff format ─────────────────────────────────────────────

step("SEARCH/REPLACE format compliance (Aider diff mode)")
DIFF_SYSTEM = """\
You are an expert Python programmer. When editing files, you MUST use SEARCH/REPLACE blocks.

Format (use EXACTLY this, including the marker lines):
<<<<<<< SEARCH
[exact original lines to find]
=======
[replacement lines]
>>>>>>> REPLACE

Never use markdown code blocks. Only use SEARCH/REPLACE blocks."""

DIFF_USER = """\
Here is solution.py:

# placeholder

Edit solution.py to replace the placeholder comment with a function called
add_numbers(a, b) that returns a + b."""

try:
    reply, elapsed = chat(
        [{"role": "system", "content": DIFF_SYSTEM},
         {"role": "user",   "content": DIFF_USER}],
        timeout=60,
    )
    show("RAW MODEL RESPONSE — SEARCH/REPLACE format", reply)
    has_search  = "<<<<<<< SEARCH" in reply
    has_replace = ">>>>>>> REPLACE" in reply
    has_sep     = "=======" in reply
    if has_search and has_replace and has_sep:
        ok(f"model produced valid SEARCH/REPLACE block  ({elapsed:.1f}s)")
    else:
        markers = [m for m, p in [
            ("<<<<<<< SEARCH",  has_search),
            ("=======",         has_sep),
            (">>>>>>> REPLACE", has_replace),
        ] if not p]
        # WARN not fail — we continue to check whole-file format which may work.
        # If SEARCH/REPLACE fails and whole-file passes, fix is --edit-format whole.
        log(f"  WARN  SEARCH/REPLACE format  {ts()}")
        log(f"        Missing markers: {markers}")
        log(f"        Model produced {len(reply)} chars but ignored the format instruction.")
        log(f"        Aider diff mode will see 'no edit' for every run with this model.")
        log(f"        Proceeding to check whole-file format (Aider's fallback)...")
except Exception as e:
    fail("SEARCH/REPLACE format", e)


# ── 4. Whole-file format ──────────────────────────────────────────────────────

step("Whole-file format compliance (Aider whole mode)")
WHOLE_SYSTEM = """\
You are an expert Python programmer. When editing files, reply with the
COMPLETE new file content inside a single Python code block.

Format:
```python
[complete file content here]
```

Include the complete file — do not omit any lines."""

WHOLE_USER = """\
Here is solution.py:

# placeholder

Rewrite solution.py completely to add a function called add_numbers(a, b)
that returns a + b."""

try:
    reply, elapsed = chat(
        [{"role": "system", "content": WHOLE_SYSTEM},
         {"role": "user",   "content": WHOLE_USER}],
        timeout=60,
    )
    show("RAW MODEL RESPONSE — whole-file format", reply)
    has_fence = "```" in reply
    has_def   = "def add_numbers" in reply
    if has_fence and has_def:
        ok(f"model produced whole-file response in code block  ({elapsed:.1f}s)")
    else:
        issues = []
        if not has_fence: issues.append("no ``` fences")
        if not has_def:   issues.append("no 'def add_numbers'")
        fail("whole-file format", f"Issues: {issues}\nResponse:\n{reply}")
except Exception as e:
    fail("whole-file format", e)


# ── 5. Realistic RALPH plan prompt ────────────────────────────────────────────

step("Realistic RALPH plan prompt (what executor actually sends)")
RALPH_PLAN = """\
Implementation Plan:
- Language: Python
- Files: solution.py (implementation), test_solution.py (pytest tests)
- Key function: add_numbers(a: float, b: float) -> float
- Success criteria: all pytest tests pass

Implementation goes in solution.py.
Tests go in test_solution.py using pytest-style functions (def test_...():).
test_solution.py MUST start with: from solution import add_numbers
Do NOT use if __name__ == '__main__': style tests.
Do NOT use unittest.TestCase.

Task: write a function that adds two numbers and returns the result, with tests"""

RALPH_PLAN_SOL = (
    RALPH_PLAN + "\n\nWrite ONLY solution.py — the implementation. No tests in this file."
)
RALPH_PLAN_TEST = (
    RALPH_PLAN + "\n\nWrite ONLY test_solution.py — pytest-style tests.\n"
    "First line must be: from solution import add_numbers\n"
    "Do NOT use unittest.TestCase."
)

try:
    log("  (testing solution.py call — same split RALPH uses)")
    reply_sol, elapsed_sol = chat(
        [{"role": "system", "content": WHOLE_SYSTEM},
         {"role": "user",   "content": RALPH_PLAN_SOL}],
        timeout=120,
    )
    show("RAW MODEL RESPONSE — realistic plan, solution.py call", reply_sol)
    has_def_sol = "def add_numbers" in reply_sol
    has_fence_sol = "```" in reply_sol
    ok(f"solution.py call: {elapsed_sol:.1f}s  fence={has_fence_sol}  has_def={has_def_sol}")

    log("  (testing test_solution.py call)")
    reply_test, elapsed_test = chat(
        [{"role": "system", "content": WHOLE_SYSTEM},
         {"role": "user",   "content": RALPH_PLAN_TEST}],
        timeout=120,
    )
    show("RAW MODEL RESPONSE — realistic plan, test_solution.py call", reply_test)
    has_import = "from solution import" in reply_test
    has_test   = "def test_" in reply_test
    ok(f"test_solution.py call: {elapsed_test:.1f}s  has_import={has_import}  has_test={has_test}")

    if not (has_def_sol and has_test):
        log("  WARN  One or both files missing expected content — Aider may still 'no edit'.")
    else:
        log("  PASS  Both split calls produce expected content. --edit-format whole should work.")
except Exception as e:
    fail("realistic RALPH plan prompt (split)", e)


log(f"\n  ALL D_model checks complete  {ts()}")
log(f"  Review the raw responses above to understand model behaviour before involving Aider.")

"""D3.5: Executor environment completeness.

Catches all assumptions the executor makes BEFORE running Aider or tests.
Run this after D3 and before D4. Every check here corresponds to a runtime
failure that was only discovered during a live RALPH run.

Rule: every runtime failure gets a diagnostic added here so the NEXT failure
is new information, not a repeat.

Checks:
  1. pytest importable from RALPH venv
  2. pytest runs and scores correctly (regex contract with evaluator)
  3. Evaluator scoring contract — known output strings map to expected scores
  4. PYTHONUTF8 / UTF-8 encoding works in subprocess env
  5. Cloud model reachable (or explicitly unavailable — not silently broken)
  6. git user.name and user.email configured (required for commits)
"""
import subprocess, sys, os, json, tempfile, shutil, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from evaluator import _score_from_tests
from config import TIMEOUT_SENTINEL

_start = time.time()
PYTHON = sys.executable


def ts():  return f"[+{time.time()-_start:5.1f}s]"
def log(msg): print(msg, flush=True)
def ok(label):  log(f"  PASS  {label}  {ts()}")
def fail(label, detail=""):
    log(f"  FAIL  {label}  {ts()}")
    for l in str(detail).splitlines(): log(f"        {l}")
    sys.exit(1)
def step(label): log(f"\n  -- {label}  {ts()}")


# ── 1. pytest importable ──────────────────────────────────────────────────────

step("pytest importable from RALPH venv")
r = subprocess.run([PYTHON, "-m", "pytest", "--version"],
                   capture_output=True, text=True, timeout=10)
if r.returncode != 0 or "pytest" not in r.stdout + r.stderr:
    fail("pytest importable",
         f"exit {r.returncode}\n{r.stdout}\n{r.stderr}\n"
         f"Fix: {PYTHON} -m pip install pytest")
ok(f"pytest {r.stdout.strip()}")


# ── 2. pytest runs and produces scoreable output ──────────────────────────────

step("pytest runs against a synthetic test file")
tmp = Path(tempfile.mkdtemp())
try:
    # Write a passing test
    (tmp / "solution.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp / "test_solution.py").write_text(
        "from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    r = subprocess.run(
        [PYTHON, "-m", "pytest", "test_solution.py", "--tb=short", "-q"],
        cwd=str(tmp), capture_output=True, text=True, timeout=30,
    )
    output = (r.stdout + r.stderr).strip()
    if "passed" not in output.lower():
        fail("pytest produces 'passed'", f"output was:\n{output}")
    ok(f"pytest output: {output[:80]}")

    # Write a failing test
    (tmp / "test_solution.py").write_text(
        "from solution import add\n\ndef test_fail():\n    assert add(1, 2) == 99\n",
        encoding="utf-8",
    )
    r2 = subprocess.run(
        [PYTHON, "-m", "pytest", "test_solution.py", "--tb=short", "-q"],
        cwd=str(tmp), capture_output=True, text=True, timeout=30,
    )
    out2 = (r2.stdout + r2.stderr).strip()
    if "failed" not in out2.lower():
        fail("pytest produces 'failed'", f"output was:\n{out2}")
    ok(f"pytest failure output: {out2[:80]}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# ── 3. Evaluator scoring contract ─────────────────────────────────────────────

step("evaluator scoring contract")

# (operator, threshold) — e.g. (">=", 0.75) means score >= 0.75
CASES = [
    ("1 passed",                   ">=", 0.75, "all tests pass -> score >= 0.75"),
    ("1 failed",                   "==", 0.20, "test failure -> score == 0.20"),
    ("no tests found",             "<",  0.75, "no tests found -> score < 0.75"),
    ("No module named pytest",     "<",  0.75, "pytest missing -> score < 0.75"),
    (TIMEOUT_SENTINEL + " detail", "==", 0.05, "timeout sentinel -> score == 0.05"),
    ("(no tests found)",           "<",  0.75, "no-test sentinel -> score < 0.75"),
]

for output, op, threshold, label in CASES:
    score, reason = _score_from_tests(output, "def f(): pass\n")
    passed = (
        (op == ">=" and score >= threshold) or
        (op == "==" and score == threshold) or
        (op == "<"  and score <  threshold)
    )
    if not passed:
        fail(f"evaluator: {label}",
             f"expected score {op} {threshold}, got score={score} reason='{reason}'")
    ok(f"evaluator '{output[:30]}' -> score={score:.2f} ({reason})")


# ── 4. UTF-8 encoding in subprocess env ───────────────────────────────────────

step("UTF-8 encoding in subprocess (PYTHONUTF8=1)")
snippet = "import sys; sys.stdout.buffer.write('\\u2588 ok\\n'.encode('utf-8')); sys.stdout.flush()"
env = os.environ.copy()
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"
# Capture as bytes so the parent's cp1252 locale doesn't corrupt the decode
r = subprocess.run([PYTHON, "-c", snippet], capture_output=True, timeout=10, env=env)
if r.returncode != 0:
    fail("UTF-8 subprocess encoding",
         f"exit {r.returncode} — subprocess raised an exception\n{r.stderr!r}")
try:
    decoded = r.stdout.decode("utf-8")
except UnicodeDecodeError as e:
    fail("UTF-8 subprocess encoding", f"stdout bytes not valid UTF-8: {e}")
if "█" not in decoded:
    fail("UTF-8 subprocess encoding",
         f"block char not in output; got: {decoded!r}")
ok("block character \\u2588 survived subprocess stdout without UnicodeEncodeError")


# ── 5. Cloud model reachable ──────────────────────────────────────────────────

step("cloud model reachable (Gemini)")
import litellm
litellm.set_verbose = False
try:
    resp = litellm.completion(
        model=config.CLOUD_MODEL,
        messages=[{"role": "user", "content": "reply with just the word pong"}],
        timeout=15, num_retries=0, max_tokens=5,
    )
    reply = resp.choices[0].message.content.strip()
    ok(f"cloud model replied: {reply[:40]!r}")
except litellm.RateLimitError as e:
    fail("cloud model: QUOTA EXHAUSTED",
         f"{e}\nGet a fresh API key from https://aistudio.google.com/app/apikey\n"
         f"and update GEMINI_API_KEY in ralph/.env")
except litellm.AuthenticationError as e:
    fail("cloud model: AUTH FAILED", f"{e}\nCheck GEMINI_API_KEY in ralph/.env")
except Exception as e:
    fail("cloud model unreachable", f"{e.__class__.__name__}: {e}")


# ── 6. git identity configured ────────────────────────────────────────────────

step("git user.name and user.email configured")
for field in ("user.name", "user.email"):
    r = subprocess.run(["git", "config", "--global", field],
                       capture_output=True, text=True, timeout=5)
    val = r.stdout.strip()
    if not val:
        fail(f"git {field} not set",
             f"Fix: git config --global {field} 'Your Value'")
    ok(f"git {field} = {val!r}")


log(f"\n  ALL D3.5 checks passed  {ts()}")

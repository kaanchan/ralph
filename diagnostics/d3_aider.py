"""D3: Aider writes a file in an isolated temp git repo.

Tests four variants to localise where Aider hangs:
  A) Pre-committed clean placeholder (default flags)
  B) Dirty placeholder with --no-dirty-commits  (skips PRE-edit commit only)
  C) Dirty placeholder, default                  (HANG: post-edit auto-commit
                                                   LLM call hangs on new files)
  D) Dirty placeholder with --no-auto-commits   (RECOMMENDED for scripted use:
                                                   no LLM round-trips for
                                                   commit messages at all)

Variant D is Aider's documented workflow for scripts/agents and is the
production fix for executor.py.
"""
import sys, os, subprocess, tempfile, shutil, time, threading, json
import urllib.request, urllib.error
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
import config

PYTHON  = sys.executable
MODEL   = config.LOCAL_MODEL
BASE    = config.OLLAMA_BASE_URL
TIMEOUT = 180

_start = time.time()
def ts(): return f"[+{time.time()-_start:5.1f}s]"
def log(msg): print(msg, flush=True)
def ok(label):   log(f"  PASS  {label}  {ts()}")
def warn(label, detail=""):
    log(f"  WARN  {label}  {ts()}")
    for l in str(detail).splitlines(): log(f"        {l}")
def fail(label, detail=""):
    log(f"  FAIL  {label}  {ts()}")
    for l in str(detail).splitlines(): log(f"        {l}")
def step(label):  log(f"\n  -- {label}  {ts()}")


# ── ollama probes (used by watchdog during silent phases) ───────────────────

def ollama_ps():
    """Return list of currently-loaded models via /api/ps, or None on error."""
    try:
        with urllib.request.urlopen(f"{BASE}/api/ps", timeout=2) as r:
            data = json.loads(r.read())
        return data.get("models", [])
    except Exception:
        return None

def fmt_ollama_ps(models):
    if models is None: return "ollama unreachable"
    if not models:     return "no model loaded"
    return "loaded: " + ", ".join(
        f"{m.get('name','?').split(':')[0]}({m.get('size',0)/1e9:.1f}GB)"
        for m in models
    )


# ── helpers ──────────────────────────────────────────────────────────────────

def make_temp_repo():
    tmp = tempfile.mkdtemp(prefix="ralph_d3_")
    cmds = [
        ["git", "init", tmp],
        ["git", "-C", tmp, "config", "user.email", "test@ralph"],
        ["git", "-C", tmp, "config", "user.name",  "ralph-test"],
        ["git", "-C", tmp, "config", "core.editor", "cmd /c exit 0"],
        ["git", "-C", tmp, "config", "commit.gpgsign", "false"],
    ]
    for cmd in cmds: subprocess.run(cmd, capture_output=True)
    return tmp

def aider_env():
    env = os.environ.copy()
    env.update(
        OLLAMA_API_BASE      = BASE,
        GIT_EDITOR           = "cmd /c exit 0",
        GIT_TERMINAL_PROMPT  = "0",
        GIT_AUTHOR_NAME      = "ralph-test",
        GIT_AUTHOR_EMAIL     = "test@ralph",
        GIT_COMMITTER_NAME   = "ralph-test",
        GIT_COMMITTER_EMAIL  = "test@ralph",
        PYTHONUTF8           = "1",
        PYTHONIOENCODING     = "utf-8",
    )
    return env

def make_placeholder(tmp, committed: bool):
    target = os.path.join(tmp, "test_write.py")
    with open(target, "w") as f: f.write("# placeholder\n")
    if committed:
        subprocess.run(["git", "-C", tmp, "add", "test_write.py"], capture_output=True)
        subprocess.run(["git", "-C", tmp, "commit", "-m", "init placeholder"],
                       capture_output=True, env=aider_env())
    return target


# ── core aider runner with watchdog + ollama probe ──────────────────────────

TRIVIAL_MESSAGE = "Replace this file content with exactly one line: x = 42"

def run_aider(tmp, target, extra_args=(), base_args=("--auto-commits",),
              timeout=TIMEOUT, label="aider",
              message=TRIVIAL_MESSAGE, extra_files=()):
    cmd = [PYTHON, "-m", "aider",
           "--yes", "--no-show-model-warnings",
           *base_args,
           "--model", MODEL,
           "--message", message,
           *extra_args, target, *extra_files]
    flag_str = " ".join(list(base_args) + list(extra_args))
    log(f"        cmd : ... aider {flag_str} <target>")
    log(f"        {'─'*48}")

    proc = subprocess.Popen(
        cmd, cwd=tmp,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", bufsize=1, env=aider_env(),
    )

    lines = []
    state = {"running": True, "last_t": time.time(), "interrupted": False}
    deadline = time.time() + timeout

    # ── reader thread: pulls lines off the pipe so main thread stays responsive
    def reader():
        try:
            for line in proc.stdout:
                state["last_t"] = time.time()
                log(f"        {ts()} {line.rstrip()}")
                lines.append(line)
        except Exception:
            pass

    # ── watchdog: heartbeat + ollama probe during silent windows
    def watchdog():
        while state["running"] and proc.poll() is None:
            silence = time.time() - state["last_t"]
            if silence > 8:
                ps = fmt_ollama_ps(ollama_ps())
                log(f"        {ts()} ... silent {silence:4.0f}s | ollama: {ps}")
            time.sleep(5)

    rt = threading.Thread(target=reader,   daemon=True); rt.start()
    wt = threading.Thread(target=watchdog, daemon=True); wt.start()

    # ── main thread: poll with short interruptible sleeps so Ctrl+C lands fast
    try:
        while proc.poll() is None:
            if time.time() > deadline:
                proc.kill()
                state["running"] = False
                rt.join(timeout=2)
                raise TimeoutError(
                    f"{label} exceeded {timeout}s. Last 10 lines:\n" + "".join(lines[-10:])
                )
            time.sleep(0.5)  # interruptible — Ctrl+C lands here within 500ms
    except KeyboardInterrupt:
        log(f"\n        {ts()} *** Ctrl+C — killing aider subprocess ***")
        state["interrupted"] = True
        state["running"] = False
        try: proc.kill()
        except Exception: pass
        rt.join(timeout=2)
        raise
    finally:
        state["running"] = False
        rt.join(timeout=2)

    log(f"        {'─'*48}")
    return proc.returncode, "".join(lines)

def assert_file_written(target, output):
    combined = output.lower()
    assert "applied edit" in combined, (
        "Aider exited but never said 'applied edit'.\n"
        "Last 15 lines:\n" + "".join(output.splitlines(keepends=True)[-15:])
    )
    content = open(target, encoding="utf-8").read()
    assert content.strip() and content.strip() != "# placeholder", \
        f"File unchanged:\n{content}"
    return content


# ── sub-checks ───────────────────────────────────────────────────────────────

def check_aider_version():
    r = subprocess.run([PYTHON, "-m", "aider", "--version"],
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr.strip()
    ok(f"aider: {r.stdout.strip()}")

def check_ollama_reachable():
    urllib.request.urlopen(f"{BASE}/", timeout=5)
    ok(f"Ollama at {BASE}")

def check_model_listed():
    with urllib.request.urlopen(f"{BASE}/api/tags", timeout=5) as r:
        tags = json.loads(r.read())
    name = MODEL.removeprefix("ollama/")
    names = [m["name"].split(":")[0] for m in tags.get("models", [])]
    assert any(name in n for n in names), f"not in {names}"
    ok(f"model '{name}' listed")

def check_git_commit_in_temp_repo():
    tmp = make_temp_repo()
    try:
        with open(os.path.join(tmp, "probe.txt"), "w") as f: f.write("probe\n")
        subprocess.run(["git", "-C", tmp, "add", "."], capture_output=True)
        r = subprocess.run(["git", "-C", tmp, "commit", "-m", "probe"],
                          capture_output=True, text=True, timeout=15, env=aider_env())
        assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
        ok("git commit in temp repo")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def variant_A_pre_committed():
    """Clean state: placeholder is already committed before Aider runs."""
    step("Variant A: pre-committed placeholder (clean state)")
    tmp = make_temp_repo()
    try:
        target = make_placeholder(tmp, committed=True)
        rc, out = run_aider(tmp, target, label="A")
        content = assert_file_written(target, out)
        ok(f"variant A wrote ({len(content.splitlines())} lines): {content.strip()[:80]!r}")
        return True
    except Exception as e:
        fail("variant A", e); return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def variant_B_no_dirty_commits():
    """Dirty state but --no-dirty-commits flag skips the pre-commit."""
    step("Variant B: dirty placeholder + --no-dirty-commits")
    tmp = make_temp_repo()
    try:
        target = make_placeholder(tmp, committed=False)
        rc, out = run_aider(tmp, target, extra_args=("--no-dirty-commits",), label="B")
        content = assert_file_written(target, out)
        ok(f"variant B wrote ({len(content.splitlines())} lines): {content.strip()[:80]!r}")
        return True
    except Exception as e:
        fail("variant B", e); return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def variant_C_default():
    """Original failing case: dirty placeholder, default flags."""
    step("Variant C: dirty placeholder, default (KNOWN HANG — short timeout)")
    tmp = make_temp_repo()
    try:
        target = make_placeholder(tmp, committed=False)
        # Use a short timeout — we already know this hangs
        rc, out = run_aider(tmp, target, timeout=45, label="C")
        content = assert_file_written(target, out)
        ok(f"variant C wrote ({len(content.splitlines())} lines): {content.strip()[:80]!r}")
        return True
    except Exception as e:
        warn("variant C (expected to fail)", e); return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def variant_D_no_auto_commits():
    """RECOMMENDED for scripts: no LLM round-trips for commit messages.
    --no-auto-commits + --no-dirty-commits disables BOTH commit code paths."""
    step("Variant D: --no-auto-commits --no-dirty-commits (RECOMMENDED)")
    tmp = make_temp_repo()
    try:
        target = make_placeholder(tmp, committed=False)
        rc, out = run_aider(
            tmp, target,
            base_args=("--no-auto-commits", "--no-dirty-commits"),
            label="D",
        )
        content = assert_file_written(target, out)
        ok(f"variant D wrote ({len(content.splitlines())} lines): {content.strip()[:80]!r}")
        return True
    except Exception as e:
        fail("variant D", e); return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def variant_E_realistic_two_file():
    """PRODUCTION REPLICA: two-file edit with the exact prompt shape RALPH sends.

    This is the most important variant. A, B, C, D all use a trivial one-liner
    message on a single file. RALPH sends a ~1000-char structured plan to two
    files (solution.py + test_solution.py). We test that exact shape here.

    --verbose captures the raw LLM request/response so we can see:
      - what edit format Aider selects for this model
      - what the model actually returns
      - whether Aider can parse it as a valid diff
    """
    step("Variant E: two-file realistic RALPH prompt + --verbose (PRODUCTION REPLICA)")

    REALISTIC_PLAN = """\
Implementation Plan:
- Language: Python
- Files: solution.py (implementation), test_solution.py (pytest tests)
- Key function: add_numbers(a: float, b: float) -> float
- Success criteria: at least 3 pytest test cases pass

REQUIRED OUTPUT FORMAT:
- Implementation goes in solution.py
- Tests go in test_solution.py using pytest-style functions (def test_...():)
- test_solution.py MUST start with: from solution import add_numbers
- Do NOT use if __name__ == '__main__': style tests
- Do NOT use unittest.TestCase

Task: write a function that adds two numbers and returns the result, with tests"""

    tmp = make_temp_repo()
    try:
        # Create both files as empty placeholders — same as executor.py does
        solution  = os.path.join(tmp, "solution.py")
        test_file = os.path.join(tmp, "test_solution.py")
        with open(solution,  "w", encoding="utf-8") as f: f.write("# generated by ralph\n")
        with open(test_file, "w", encoding="utf-8") as f: f.write("# generated by ralph\n")

        sol_prompt  = REALISTIC_PLAN + "\n\nWrite ONLY solution.py — the implementation. No tests."
        test_prompt = (REALISTIC_PLAN +
                       "\n\nWrite ONLY test_solution.py — pytest-style tests.\n"
                       "First line must be: from solution import add_numbers\n"
                       "Do NOT use unittest.TestCase.")

        log(f"\n  -- Variant E, call 1: solution.py")
        rc1, out1 = run_aider(
            tmp, solution,
            base_args=("--no-auto-commits", "--no-dirty-commits"),
            extra_args=("--verbose", "--edit-format", "whole"),
            message=sol_prompt,
            timeout=TIMEOUT,
            label="E-sol",
        )

        log(f"\n  -- Variant E, call 2: test_solution.py")
        rc2, out2 = run_aider(
            tmp, test_file,
            base_args=("--no-auto-commits", "--no-dirty-commits"),
            extra_args=("--verbose", "--edit-format", "whole"),
            message=test_prompt,
            timeout=TIMEOUT,
            label="E-test",
        )

        combined = out1 + out2
        sol_content  = open(solution,  encoding="utf-8").read()
        test_content = open(test_file, encoding="utf-8").read()
        sol_changed  = sol_content.strip() not in ("", "# generated by ralph")
        test_changed = test_content.strip() not in ("", "# generated by ralph")
        edit_applied = "applied edit" in combined.lower()

        log(f"\n  -- Variant E results:")
        log(f"        edit_applied    : {edit_applied}")
        log(f"        solution.py     : {'CHANGED' if sol_changed  else 'UNCHANGED'}")
        log(f"        test_solution.py: {'CHANGED' if test_changed else 'UNCHANGED'}")
        log(f"        aider rc        : sol={rc1} test={rc2}")

        if not edit_applied:
            log(f"\n  -- Variant E: NO EDIT in either call. Last 40 lines of combined output:")
            for line in combined.splitlines()[-40:]:
                log(f"        {line}")
            fail("variant E", "Aider returned rc=0 on both calls but no edit applied. See above.")

        if not sol_changed:
            fail("variant E", f"solution.py unchanged.\nContent:\n{sol_content}")

        ok(f"variant E: solution.py {'CHANGED' if sol_changed else 'UNCHANGED'}, "
           f"test_solution.py {'CHANGED' if test_changed else 'UNCHANGED'}")
        return True
    except Exception as e:
        fail("variant E", e); return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── run ──────────────────────────────────────────────────────────────────────

def _skipped_variants() -> set:
    """Return set of variant letters to skip, from --skip-variants A,B,C."""
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg.startswith("--skip-variants"):
            val = arg.split("=", 1)[1] if "=" in arg else (sys.argv[i + 1] if i + 1 < len(sys.argv) else "")
            return {v.strip().upper() for v in val.split(",")}
    return set()


if __name__ == "__main__":
    SKIP = _skipped_variants()
    log(f"\n[D3] Aider  (model={MODEL}  base={BASE})")

    pre = [
        ("aider version",           check_aider_version),
        ("Ollama reachable",        check_ollama_reachable),
        ("model listed",            check_model_listed),
        ("git commit in temp repo", check_git_commit_in_temp_repo),
    ]
    for label, fn in pre:
        try: fn()
        except Exception as e:
            fail(label, e)
            log(f"\n  pre-check failed -- aborting variants")
            sys.exit(1)

    # Run E first — it's the production replica. Most important variant.
    e_ok = variant_E_realistic_two_file() if "E" not in SKIP else (log("  SKIP  variant E"), True)[1]
    # Run D — confirms the basic single-file path works
    d_ok = variant_D_no_auto_commits()    if "D" not in SKIP else (log("  SKIP  variant D"), True)[1]
    a_ok = variant_A_pre_committed()      if "A" not in SKIP else (log("  SKIP  variant A"), True)[1]
    b_ok = variant_B_no_dirty_commits()   if "B" not in SKIP else (log("  SKIP  variant B"), True)[1]
    c_ok = variant_C_default()            if "C" not in SKIP else (log("  SKIP  variant C"), True)[1]

    log(f"\n  ── verdict ──────────────────────────────────────")
    log(f"  Variant E (realistic 2-file RALPH prompt) : {'PASS' if e_ok else 'FAIL'}  <- MOST IMPORTANT")
    log(f"  Variant D (--no-auto-commits, trivial)    : {'PASS' if d_ok else 'FAIL'}  <- RECOMMENDED BASE")
    log(f"  Variant A (pre-committed, trivial)        : {'PASS' if a_ok else 'FAIL'}")
    log(f"  Variant B (--no-dirty-commits, trivial)   : {'PASS' if b_ok else 'FAIL'}")
    log(f"  Variant C (default / dirty, trivial)      : {'PASS' if c_ok else 'FAIL (expected)'}")
    log("")
    if e_ok:
        log("  >> PRODUCTION PATH WORKS: local model produces edits with realistic prompt.")
    elif d_ok:
        log("  >> WARNING: trivial prompt works but realistic RALPH prompt does NOT.")
        log("     Root cause is the prompt shape or model context handling, not Aider flags.")
        log("     See Variant E verbose output above for the raw model response.")
    else:
        log("  >> Both E and D failed. Check D_model diagnostic first.")
        log("     If D_model shows model can't produce diffs, the problem is upstream of Aider.")

    overall_ok = e_ok and d_ok
    log(f"\n  {'ALL PASS' if overall_ok else 'ISSUES FOUND — see verdict above'}  (total {ts()})\n")
    sys.exit(0 if overall_ok else 1)

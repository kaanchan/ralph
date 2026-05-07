"""Run all diagnostics in dependency order. Stops at first failure.
All output is written live to diag_latest.log AND printed to console.

Usage:
    python diagnostics/run_all.py          # all checks
    python diagnostics/run_all.py --fast   # skip D6 (slow integration test)

Tail the log in a second terminal BEFORE running:
    PowerShell:  Get-Content -Wait diagnostics\\diag_latest.log
    Git Bash:    tail -f diagnostics/diag_latest.log
"""
import os, sys

# Self-relaunch with PYTHONUTF8=1 if not already set so that this process AND
# all subprocess children use UTF-8 for stdin/stdout/stderr. Without this,
# Windows defaults to cp1252 which crashes on any Unicode diagnostic output.
if not os.getenv("PYTHONUTF8"):
    import subprocess as _sp
    _env = os.environ.copy()
    _env["PYTHONUTF8"] = "1"
    _env["PYTHONIOENCODING"] = "utf-8"
    sys.exit(_sp.run([sys.executable] + sys.argv, env=_env).returncode)

import subprocess, datetime, shutil, time, threading
from pathlib import Path

DIAGS = [
    ("D1", "d1_ollama.py",     "Ollama server + model"),
    ("D2", "d2_litellm.py",    "LiteLLM -> Ollama"),
    ("D3",   "d3_aider.py",          "Aider writes a file"),
    ("D3.5", "d3_5_executor_env.py", "Executor environment completeness"),
    ("D4",   "d4_langgraph.py",      "LangGraph graph streams"),
    ("D5", "d5_langsmith.py",  "LangSmith tracing"),
    ("D6", "d6_ralph_loop.py", "Full RALPH loop (slow ~3 min)"),
]

SKIP_D6 = "--fast" in sys.argv

# --skip-variants A,B  ->  passed through to d3_aider.py
_sv_idx = next((i for i, a in enumerate(sys.argv) if a.startswith("--skip-variants")), None)
D3_EXTRA = []
if _sv_idx is not None:
    arg = sys.argv[_sv_idx]
    if "=" in arg:
        D3_EXTRA = [arg]
    elif _sv_idx + 1 < len(sys.argv):
        D3_EXTRA = [arg, sys.argv[_sv_idx + 1]]

HERE = Path(__file__).parent
LATEST = HERE / "diag_latest.log"
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def emit(line: str, log):
    print(line, end="", flush=True)
    log.write(line)
    log.flush()

def run_streaming(script: Path, log, extra_args=()) -> int:
    """Stream subprocess output line-by-line in a reader thread so the main
    thread can respond to Ctrl+C within ~500ms (vs blocking forever in
    `for line in proc.stdout` on Windows)."""
    proc = subprocess.Popen(
        [sys.executable, str(script), *extra_args],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )

    def reader():
        try:
            for line in proc.stdout:
                emit(line, log)
        except Exception:
            pass

    rt = threading.Thread(target=reader, daemon=True)
    rt.start()

    try:
        while proc.poll() is None:
            time.sleep(0.5)  # interruptible
    except KeyboardInterrupt:
        emit("\n*** Ctrl+C — terminating subprocess ***\n", log)
        try: proc.kill()
        except Exception: pass
        rt.join(timeout=2)
        raise

    rt.join(timeout=2)
    return proc.returncode

# Write live to diag_latest.log; archive timestamped copy at the end
LATEST.unlink(missing_ok=True)
all_passed = True

ARCHIVED = HERE / f"diag_{ts}.log"

with open(LATEST, "w", encoding="utf-8") as log:
    emit(f"\n{'='*56}\n  RALPH diagnostics  {ts}\n{'='*56}\n", log)
    emit(f"  Log: {LATEST}\n", log)

    try:
        for tag, script, label in DIAGS:
            if tag == "D6" and SKIP_D6:
                emit(f"\n  SKIP  {tag} {label}  (--fast)\n", log)
                continue

            emit(f"\n{'─'*56}\n  >> {tag}: {label}\n{'─'*56}\n", log)
            t0 = time.time()
            extra = D3_EXTRA if tag == "D3" else ()
            rc = run_streaming(HERE / script, log, extra_args=extra)
            elapsed = time.time() - t0
            emit(f"  -- {tag} finished in {elapsed:.1f}s  rc={rc}\n", log)

            if rc != 0:
                emit(
                    f"\n{'='*56}\n"
                    f"  STOPPED at {tag}: {label}\n"
                    f"  Fix {tag} before continuing.\n"
                    f"{'='*56}\n",
                    log,
                )
                all_passed = False
                break

        if all_passed:
            emit(f"\n{'='*56}\n  ALL diagnostics passed\n{'='*56}\n", log)
    except KeyboardInterrupt:
        emit(f"\n{'='*56}\n  INTERRUPTED by user\n{'='*56}\n", log)
        all_passed = False

# Archive a timestamped copy for the record
shutil.copy(LATEST, ARCHIVED)
print(f"\n  Live log : {LATEST}\n  Archived : {ARCHIVED}\n", flush=True)

sys.exit(0 if all_passed else 1)

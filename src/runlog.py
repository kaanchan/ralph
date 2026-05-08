"""Live run log — tail-able by `Get-Content -Wait ralph_run.log` in another terminal.

All long-running operations (LLM calls, Aider subprocess) write here as they
happen, so a hang is visible in real time instead of being a 5-minute black box.
"""
import datetime
import json
import sys
import urllib.request
from pathlib import Path
from config import OLLAMA_API_BASE, RALPH_LOG_PATH


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def log(msg: str, *, also_console: bool = True) -> None:
    """Append a line to ralph_run.log. Best-effort — never raises on disk error."""
    line = f"[{_ts()}] {msg}\n"
    try:
        with open(RALPH_LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
            f.write(line)
    except OSError:
        pass
    if also_console:
        try:
            sys.stdout.write(line)
            sys.stdout.flush()
        except Exception:
            pass


def reset_log() -> None:
    """Truncate the log at the start of a run so it always reflects the current run."""
    try:
        Path(RALPH_LOG_PATH).write_text(
            f"=== RALPH run started {datetime.datetime.now().isoformat(timespec='seconds')} ===\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def ollama_ps() -> str:
    """Snapshot of /api/ps so timeout messages show whether the model is actually loaded."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_API_BASE}/api/ps", timeout=2) as r:
            data = json.loads(r.read().decode("utf-8"))
        models = data.get("models", [])
        if not models:
            return "ollama: no models loaded"
        parts = [f"{m.get('name','?')}({(m.get('size_vram') or m.get('size') or 0) / 1e9:.1f}GB)"
                 for m in models]
        return "ollama loaded: " + ", ".join(parts)
    except Exception as e:
        return f"ollama unreachable ({e.__class__.__name__})"


def loud_timeout(call: str, budget: int, extra: str = "") -> None:
    """Big visible block when a timeout fires — designed to surface in a glance."""
    bar = "*" * 56
    log(f"\n{bar}", also_console=True)
    log(f"*** RALPH TIMEOUT — {call}", also_console=True)
    log(f"***   budget : {budget}s", also_console=True)
    log(f"***   ollama : {ollama_ps()}", also_console=True)
    if extra:
        log(f"***   note   : {extra}", also_console=True)
    log(f"{bar}\n", also_console=True)

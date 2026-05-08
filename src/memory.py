"""JSON-file memory — persists run history for analysis and future recall."""
import json
from datetime import datetime, timezone
from pathlib import Path
from config import MEMORY_DIR
from state import RalphState


def save_run(state: RalphState) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = MEMORY_DIR / f"run_{ts}.json"
    record = {
        "timestamp": ts,
        "task": state["task"],
        "iterations": state["iterations"],
        "final_score": state["score"],
        "escalated": state["escalated"],
        "model_used": state["model_used"],
        "done": state["done"],
        "log": state["log"],
    }
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out


def load_runs() -> list[dict]:
    runs = []
    for f in sorted(MEMORY_DIR.glob("run_*.json")):
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return runs

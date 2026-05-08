import json
import threading
from pathlib import Path
from config import LOGS_DIR

STATE_FILE = LOGS_DIR / "live_state.json"
_lock = threading.Lock()

_current_state = {
    "task": "",
    "repo_dir": "",
    "iterations": 0,
    "plan": "",
    "code": "",
    "test_output": "",
    "score": 0.0,
    "status": "Initializing...",
    "logs": []
}

def export_state(new_state_dict: dict):
    with _lock:
        _current_state.update(new_state_dict)
        _write_to_disk()

def add_log_line(line: str):
    with _lock:
        _current_state["logs"].append(line)
        if len(_current_state["logs"]) > 50:
            _current_state["logs"].pop(0)
        _write_to_disk()

def _write_to_disk():
    try:
        STATE_FILE.write_text(json.dumps(_current_state, indent=2), encoding="utf-8")
    except OSError:
        pass

"""Central configuration — change models and thresholds here."""
import os
from pathlib import Path

# ── Model selection ──────────────────────────────────────────────────────────
LOCAL_MODEL = "ollama/qwen25-coder-14b"
CLOUD_MODEL = "gemini/gemini-2.0-flash"
OLLAMA_BASE_URL = "http://localhost:11434"

# ── Loop control ─────────────────────────────────────────────────────────────
MAX_ITERATIONS = 5          # hard stop
ESCALATE_AFTER = 3          # switch to cloud after this many retries
SCORE_SUCCESS = 0.75        # evaluator score that counts as done

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
WORKSPACE_DIR = ROOT / "workspace"
MEMORY_DIR = ROOT / "memory"
MEMORY_DIR.mkdir(exist_ok=True)

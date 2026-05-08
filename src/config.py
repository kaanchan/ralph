"""Central configuration — change models and thresholds here.

Timeouts are intentionally short. Local-model hangs are common; we want fast
failure that propagates to user attention rather than 5-minute silent waits.
All timeouts are env-overridable so you can tune per-task without code edits:

    RALPH_TIMEOUT_LLM=20    python main.py ...
    RALPH_TIMEOUT_AIDER=60  python main.py ...
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── Model selection ──────────────────────────────────────────────────────────
LOCAL_MODEL = "ollama/qwen25-coder-14b"
CLOUD_MODEL = "gemini/gemini-2.5-flash"
OLLAMA_API_BASE  = "http://localhost:11434"   # both router (LiteLLM) and executor (Aider env)
OLLAMA_BASE_URL  = OLLAMA_API_BASE           # alias — keeps older diagnostic files working

# ── Loop control ─────────────────────────────────────────────────────────────
MAX_ITERATIONS = 5          # hard stop
ESCALATE_AFTER = 4          # switch to cloud after this many retries
SCORE_SUCCESS = 0.75        # evaluator score that counts as done
MAX_CONSECUTIVE_TIMEOUTS = 2  # 2 timeouts in a row → hard fail (don't burn the loop)

# ── Timeouts (seconds, env-overridable) ──────────────────────────────────────
LLM_TIMEOUT_SHORT  = int(os.getenv("RALPH_TIMEOUT_LLM",        30))   # planner / single LLM call
LOCAL_MODEL_TIMEOUT= int(os.getenv("RALPH_TIMEOUT_LOCAL",      180))  # direct Ollama generation (longer for complex prompts)
AIDER_TIMEOUT      = int(os.getenv("RALPH_TIMEOUT_AIDER",       90))  # Aider subprocess incl. startup
GIT_TIMEOUT        = int(os.getenv("RALPH_TIMEOUT_GIT",         10))
SILENT_WARN_AFTER  = int(os.getenv("RALPH_SILENT_WARN",         15))  # warn (don't kill) at this point

# Sentinel returned by router/executor on timeout. Evaluator detects it.
TIMEOUT_SENTINEL = "<<RALPH_TIMEOUT>>"

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
WORKSPACE_DIR = ROOT / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)
MEMORY_DIR = ROOT / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
RALPH_LOG_PATH  = Path(os.getenv("RALPH_LOG_PATH", LOGS_DIR / "ralph_run.log"))
TOOLS_DEBUG_PATH = LOGS_DIR / "tools_debug.log"
RALPH_VERBOSE = os.getenv("RALPH_VERBOSE", "0") == "1"
AIDER_LOG_PATH  = WORKSPACE_DIR / "aider_last.log"  # full Aider stdout, overwritten each run

# Telemetry limits
MAX_TOOL_PAYLOAD_KB = int(os.getenv("RALPH_MAX_PAYLOAD_KB", "100"))

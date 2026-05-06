"""Executor node -- runs Aider against a target git repo (not ralph itself)."""
import subprocess
import sys
from pathlib import Path
from state import RalphState
from router import select_model
from config import OLLAMA_BASE_URL


def _aider_model_flags(model: str) -> list[str]:
    flags = ["--model", model]
    if model.startswith("ollama/"):
        flags += ["--openai-api-base", OLLAMA_BASE_URL]
    return flags


def run_aider(task: str, model: str, repo_dir: Path) -> tuple[str, str]:
    """Run Aider against repo_dir with the given task. Returns (stdout, stderr)."""
    cmd = [
        sys.executable, "-m", "aider",
        "--yes",
        "--message", task,
    ] + _aider_model_flags(model)

    result = subprocess.run(
        cmd,
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.stdout, result.stderr


def run_tests(repo_dir: Path) -> str:
    """Try common test runners; return combined output."""
    for cmd in (
        [sys.executable, "-m", "pytest", "--tb=short", "-q"],
        [sys.executable, "-m", "unittest", "discover"],
    ):
        result = subprocess.run(
            cmd, cwd=str(repo_dir),
            capture_output=True, text=True, timeout=60,
        )
        output = (result.stdout + result.stderr).strip()
        if output:
            return output
    return "(no tests found)"


def executor_node(state: RalphState) -> dict:
    model = select_model(state)
    repo_dir = Path(state["repo_dir"])

    task_prompt = f"{state['plan']}\n\nTask: {state['task']}"
    stdout, stderr = run_aider(task_prompt, model, repo_dir)
    aider_out = (stdout + stderr).strip()

    test_out = run_tests(repo_dir)

    log_entry = f"[iter {state['iterations']+1}] executor -> model={model} | aider={'OK' if stdout else 'WARN:' + stderr[:80]}"
    return {
        "code": aider_out,
        "test_output": test_out,
        "model_used": model,
        "iterations": state["iterations"] + 1,
        "log": state["log"] + [log_entry],
    }

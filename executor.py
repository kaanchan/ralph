"""Executor node — calls Aider as a subprocess to write/edit code in workspace/."""
import subprocess
import sys
from pathlib import Path
from config import WORKSPACE_DIR, OLLAMA_BASE_URL
from state import RalphState
from router import select_model, llm_call


def _aider_model_flag(model: str) -> list[str]:
    """Translate LiteLLM model string to Aider's --model flag format."""
    if model.startswith("ollama/"):
        name = model.split("/", 1)[1]
        return ["--model", f"ollama/{name}"]
    if model.startswith("gemini/"):
        return ["--model", model]
    return ["--model", model]


def run_aider(task: str, model: str, target_file: str = "solution.py") -> tuple[str, str]:
    """
    Invoke Aider in workspace/ with the given task message.
    Returns (code_written, aider_output).
    """
    WORKSPACE_DIR.mkdir(exist_ok=True)
    target = WORKSPACE_DIR / target_file

    # Touch the file so Aider has something to edit
    if not target.exists():
        target.write_text("# ralph workspace\n")

    cmd = [
        sys.executable, "-m", "aider",
        "--yes",
        "--auto-commits",             # workspace has its own git, let Aider commit
        "--message", task,
        str(target),
    ] + _aider_model_flag(model)

    if model.startswith("ollama/"):
        cmd += ["--openai-api-base", OLLAMA_BASE_URL]

    result = subprocess.run(
        cmd,
        cwd=str(WORKSPACE_DIR),
        capture_output=True,
        text=True,
        timeout=300,
    )

    code = target.read_text(encoding="utf-8") if target.exists() else ""
    return code, result.stdout + result.stderr


def run_code(target_file: str = "solution.py") -> str:
    """Execute the generated file and return stdout+stderr."""
    target = WORKSPACE_DIR / target_file
    if not target.exists():
        return "No file to run."
    result = subprocess.run(
        [sys.executable, str(target)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(WORKSPACE_DIR),
    )
    return (result.stdout + result.stderr).strip() or "(no output)"


def executor_node(state: RalphState) -> dict:
    model = select_model(state)
    task_prompt = f"{state['plan']}\n\nTask: {state['task']}"

    code, aider_out = run_aider(task_prompt, model)
    test_out = run_code()

    log_entry = f"[iter {state['iterations']+1}] executor → model={model}"
    return {
        "code": code,
        "test_output": test_out,
        "model_used": model,
        "iterations": state["iterations"] + 1,
        "log": state["log"] + [log_entry],
    }

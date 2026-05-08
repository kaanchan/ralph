from state import RalphState
from config import CLOUD_MODEL
from router import llm_call
import json
from pathlib import Path

CONSULTANT_SYSTEM = """\
You are an elite AI Systems Architect. You are auditing a local, smaller LLM that failed to complete a coding task.
You will be provided with:
1. The original Task.
2. The recent event log (including Pytest errors, Timeout warnings, and parameter choices).

Your job is NOT to write the code. 
Your job is to act as a Meta-Consultant. Tell us WHY the local model likely failed (e.g. context window too small, bad prompt instructions, stuck in a repetition loop) and suggest exactly what we should tweak in our parameters or prompt injection matrix to fix it.
Keep your response under 300 words. Be concise and actionable.
"""

def cloud_consultant_node(state: RalphState) -> dict:
    """Invokes the Cloud Model to diagnose the local model's failure."""
    
    # 1. Compile the Dossier of Failure
    log_history = "\n".join(state["log"][-5:]) # Last 5 critical events
    
    dossier = f"ORIGINAL TASK:\n{state['task']}\n\n"
    dossier += f"FAILURE LOG:\n{log_history}\n\n"
    dossier += "DIAGNOSTIC REQUEST:\nWe reached you because our local model failed. What would you suggest we tweak in our Ollama parameters (num_ctx, temperature, stop tokens) or dynamic prompts so we don't reach your node next time? Be precise."

    # 2. Call the Consultant
    advice = llm_call(dossier, CLOUD_MODEL, system=CONSULTANT_SYSTEM)
    
    # 3. Log the Advice to the Task Pod
    # (The active workspace is currently in tasks/<task>/src)
    # We will put the report in the root of the task pod
    task_dir = Path(state["repo_dir"]).parent
    report_file = task_dir / "consultant_report.md"
    
    try:
        report_file.write_text(f"# Consultant Diagnosis\n\n{advice}\n", encoding="utf-8")
    except Exception:
        pass
        
    log_entry = f"[consultant] Generated architectural advice -> {report_file.name}"
    
    return {
        "consultant_advice": advice,
        "log": state["log"] + [log_entry]
    }

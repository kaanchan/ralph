from config import TIMEOUT_SENTINEL
from state import RalphState
from router import select_model, llm_call
from runlog import log

PLANNER_SYSTEM = """\
You are a software architect. Given a coding task, produce a concise implementation plan.
Be specific about: language, file structure, key functions, and success criteria.
Keep the plan under 200 words.

REQUIRED OUTPUT FORMAT — non-negotiable:
- Implementation goes in solution.py
- Tests go in a SEPARATE file test_solution.py using pytest-style functions (def test_...():)
- test_solution.py MUST start with: from solution import <the_function_name>
- Do NOT use if __name__ == "__main__": style tests — the evaluator cannot score them
- Do NOT use unittest.TestCase — use bare pytest functions only
"""

def planner_node(state: RalphState) -> dict:
    model = select_model(state)
    plan = llm_call(state["task"], model, system=PLANNER_SYSTEM)

    if plan == TIMEOUT_SENTINEL:
        log_entry = f"[iter {state['iterations']}] planner -> model={model} | TIMEOUT"
        log(f"    planner -> model={model} | TIMEOUT")
        return {
            "plan": f"(no plan — planner timed out)\nTask: {state['task']}",
            "model_used": model,
            "timeout_count": state.get("timeout_count", 0) + 1,
            "log": state["log"] + [log_entry],
        }

    log_entry = f"[iter {state['iterations']}] planner -> model={model}"
    log(f"    planner -> model={model}")
    return {
        "plan": plan,
        "model_used": model,
        "timeout_count": 0,
        "log": state["log"] + [log_entry],
    }

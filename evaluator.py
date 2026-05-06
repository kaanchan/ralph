"""Evaluator node — scores executor output and sets done flag."""
from state import RalphState
from router import select_model, llm_call
from config import SCORE_SUCCESS

EVAL_SYSTEM = """\
You are a code quality evaluator. Given a task, generated code, and its test output,
score the solution on a scale of 0.0 to 1.0.

Scoring guide:
  1.0 = correct, clean, runs without errors
  0.8 = mostly correct, minor issues, runs
  0.5 = partial solution or has warnings
  0.2 = wrong approach or runtime errors
  0.0 = empty or completely wrong

Reply with ONLY a JSON object: {"score": 0.85, "reason": "one sentence"}
"""


def evaluator_node(state: RalphState) -> dict:
    model = select_model(state)

    prompt = f"""\
Task: {state['task']}

Generated code:
```python
{state['code']}
```

Test output:
{state['test_output']}

Score the solution."""

    raw = llm_call(prompt, model, system=EVAL_SYSTEM)

    # Parse score robustly — find first JSON-like object
    import re, json
    score = 0.0
    reason = raw
    match = re.search(r'\{[^}]+\}', raw)
    if match:
        try:
            obj = json.loads(match.group())
            score = float(obj.get("score", 0.0))
            reason = obj.get("reason", raw)
        except (json.JSONDecodeError, ValueError):
            pass

    done = score >= SCORE_SUCCESS
    log_entry = f"[iter {state['iterations']}] evaluator → score={score:.2f} done={done} | {reason}"

    return {
        "score": score,
        "done": done,
        "log": state["log"] + [log_entry],
    }

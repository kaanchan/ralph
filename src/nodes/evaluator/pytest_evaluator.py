"""Evaluator node -- scores output using test results; LLM as fallback."""
import re
from state import RalphState
from config import SCORE_SUCCESS, TIMEOUT_SENTINEL


def _score_from_tests(test_output: str, code: str) -> tuple[float, str]:
    """Derive a score from test runner output without an LLM call."""
    if test_output.startswith(TIMEOUT_SENTINEL):
        return 0.05, "executor timed out"

    if not test_output or test_output == "(no tests found)":
        lines = [l for l in code.splitlines() if l.strip() and not l.strip().startswith("#")]
        if len(lines) > 3:
            return 0.5, "no tests found but code has content"
        return 0.1, "no tests and minimal code"

    low = test_output.lower()

    if "passed" in low and "failed" not in low and "error" not in low:
        return 0.95, "all tests passed"
    if "ok" in low and "error" not in low and "fail" not in low:
        return 0.95, "unittest OK"

    m = re.search(r"(\d+) passed", low)
    if m and int(m.group(1)) > 0:
        fail_m = re.search(r"(\d+) failed", low)
        if fail_m:
            ratio = int(m.group(1)) / (int(m.group(1)) + int(fail_m.group(1)))
            return round(ratio * 0.8, 2), f"{m.group(1)} passed / {fail_m.group(1)} failed"
        return 0.8, f"{m.group(1)} tests passed"

    if any(k in low for k in ("failed", "error", "traceback", "assertionerror")):
        return 0.2, "tests failed"

    return 0.4, "unclear test result"


from runlog import log

def evaluator_node(state: RalphState) -> dict:
    score, reason = _score_from_tests(state["test_output"], state["code"])
    done = score >= SCORE_SUCCESS

    log_entry = f"[iter {state['iterations']}] evaluator -> score={score:.2f} done={done} | {reason}"
    log(f"    evaluator -> score={score:.2f} done={done} | {reason}")
    return {
        "score": score,
        "done": done,
        "log": state["log"] + [log_entry],
    }

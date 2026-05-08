"""RalphState -- the single dict that flows through the entire graph."""
from typing import TypedDict


class RalphState(TypedDict):
    task: str               # original user request
    repo_dir: str           # path to the target git repo Aider works on
    plan: str               # planner's decomposed approach
    code: str               # aider output (stdout) from last executor run
    test_output: str        # test runner output after each executor run
    score: float            # evaluator's confidence (0.0 - 1.0)
    iterations: int         # how many executor->evaluator cycles have run
    model_used: str         # which model is active this cycle
    escalated: bool         # True once we've switched to the cloud model
    done: bool              # True if score >= SCORE_SUCCESS
    timeout_count: int      # Number of consecutive timeouts
    consultant_advice: str  # Diagnostics from the cloud node
    log: list[str]          # Human-readable decision trail of decisions

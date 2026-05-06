"""RalphState — the single dict that flows through the entire graph."""
from typing import TypedDict


class RalphState(TypedDict):
    task: str           # original user request
    plan: str           # planner's decomposed approach
    code: str           # most recent code/output produced by executor
    test_output: str    # stdout/stderr from running the code
    score: float        # evaluator's confidence (0.0 – 1.0)
    iterations: int     # how many executor→evaluator cycles have run
    model_used: str     # which model is active this cycle
    escalated: bool     # True once we've switched to the cloud model
    done: bool          # terminal flag set by evaluator
    log: list[str]      # human-readable trail of decisions

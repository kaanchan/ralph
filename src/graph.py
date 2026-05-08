"""LangGraph assembly — wires planner, executor, evaluator, and router into
the RALPH loop state machine.

Graph topology:
  START -> planner -> executor -> evaluator -> [router decides] -> executor / escalate / END
                                                             ↑__________________________↓
"""
from langgraph.graph import StateGraph, END
from config import TIMEOUT_SENTINEL
from state import RalphState
from router import select_model, llm_call, route_decision
from executor import executor_node
from evaluator import evaluator_node
from telemetry import tracer

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
        # Planner timed out: increment counter so route_decision can hard-fail
        # after MAX_CONSECUTIVE_TIMEOUTS, but still let executor try with a
        # minimal plan so we don't lose the iteration entirely on a single hiccup.
        log_entry = f"[iter {state['iterations']}] planner -> model={model} | TIMEOUT"
        return {
            "plan": f"(no plan — planner timed out)\nTask: {state['task']}",
            "model_used": model,
            "timeout_count": state.get("timeout_count", 0) + 1,
            "log": state["log"] + [log_entry],
        }

    log_entry = f"[iter {state['iterations']}] planner -> model={model}"
    return {
        "plan": plan,
        "model_used": model,
        "timeout_count": 0,
        "log": state["log"] + [log_entry],
    }


def escalate_node(state: RalphState) -> dict:
    """Flip the escalated flag so subsequent calls use the cloud model."""
    log_entry = f"[iter {state['iterations']}] escalating -> switching to cloud model"
    return {
        "escalated": True,
        "timeout_count": 0,   # fresh start on cloud
        "log": state["log"] + [log_entry],
    }


def wrap_node(name, node_func):
    def wrapper(state):
        tracer.start_node(name)
        result = node_func(state)
        tracer.end_node(name, status="success")
        return result
    return wrapper


def build_graph(checkpointer=None):
    g = StateGraph(RalphState)

    g.add_node("planner", wrap_node("planner", planner_node))
    g.add_node("executor", wrap_node("executor", executor_node))
    g.add_node("evaluator", wrap_node("evaluator", evaluator_node))
    g.add_node("escalate", wrap_node("escalate", escalate_node))

    g.set_entry_point("planner")
    g.add_edge("planner", "executor")
    g.add_edge("executor", "evaluator")
    g.add_edge("escalate", "executor")

    g.add_conditional_edges(
        "evaluator",
        route_decision,
        {
            "executor": "executor",
            "escalate": "escalate",
            END: END,
        },
    )

    return g.compile(checkpointer=checkpointer)

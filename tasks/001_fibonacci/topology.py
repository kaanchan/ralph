"""Default topology for simple coding tasks.
planner -> executor -> evaluator -> [router] -> executor / escalate / END
"""
from langgraph.graph import StateGraph, END
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from state import RalphState
from nodes.planner.default_planner import planner_node
from nodes.executor.default_executor import executor_node
from nodes.evaluator.pytest_evaluator import evaluator_node
from router import route_decision
from telemetry import tracer


def wrap_node(name, node_func):
    def wrapper(state):
        tracer.start_node(name)
        result = node_func(state)
        tracer.end_node(name, status="success")
        return result
    return wrapper


def escalate_node(state: RalphState) -> dict:
    """Flip the escalated flag so subsequent calls use the cloud model."""
    log_entry = f"[iter {state['iterations']}] escalating -> switching to cloud model"
    return {
        "escalated": True,
        "timeout_count": 0,
        "log": state["log"] + [log_entry],
    }


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

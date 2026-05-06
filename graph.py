"""
LangGraph assembly — wires planner, executor, evaluator, and router into
the RALPH loop state machine.

Graph topology:
  START → planner → executor → evaluator → [router decides] → executor / escalate / END
                                                             ↑__________________________↓
"""
from langgraph.graph import StateGraph, END
from state import RalphState
from router import select_model, llm_call, route_decision
from executor import executor_node
from evaluator import evaluator_node

PLANNER_SYSTEM = """\
You are a software architect. Given a coding task, produce a concise implementation plan.
Be specific about: language, file structure, key functions, and success criteria.
Keep the plan under 200 words.
"""


def planner_node(state: RalphState) -> dict:
    model = select_model(state)
    plan = llm_call(state["task"], model, system=PLANNER_SYSTEM)
    log_entry = f"[iter {state['iterations']}] planner → model={model}"
    return {
        "plan": plan,
        "model_used": model,
        "log": state["log"] + [log_entry],
    }


def escalate_node(state: RalphState) -> dict:
    """Flip the escalated flag so subsequent calls use the cloud model."""
    log_entry = f"[iter {state['iterations']}] escalating → switching to cloud model"
    return {
        "escalated": True,
        "log": state["log"] + [log_entry],
    }


def build_graph() -> "CompiledGraph":
    g = StateGraph(RalphState)

    g.add_node("planner", planner_node)
    g.add_node("executor", executor_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("escalate", escalate_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "executor")
    g.add_edge("executor", "evaluator")
    g.add_edge("escalate", "executor")   # after escalation, retry with cloud model

    g.add_conditional_edges(
        "evaluator",
        route_decision,
        {
            "executor": "executor",
            "escalate": "escalate",
            END: END,
        },
    )

    return g.compile()

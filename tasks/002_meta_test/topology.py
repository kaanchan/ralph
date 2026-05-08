from langgraph.graph import StateGraph, END
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from state import RalphState
from nodes.planner.default_planner import planner_node
from nodes.executor.default_executor import executor_node
from nodes.evaluator.pytest_evaluator import evaluator_node
from nodes.consultant.cloud_consultant import cloud_consultant_node
from router import route_decision
from telemetry import tracer

def wrap_node(name, node_func):
    def wrapper(state):
        tracer.start_node(name)
        result = node_func(state)
        tracer.end_node(name, status="success")
        return result
    return wrapper

def meta_route_decision(state: RalphState) -> str:
    """Custom router for the meta-test pod. 
    Instead of escalating to Aider, it triggers the Cloud Consultant."""
    
    # Check circuit breakers from original router logic
    original_decision = route_decision(state)
    
    if original_decision == "escalate":
        return "consultant"
        
    return original_decision

def build_graph(checkpointer=None):
    g = StateGraph(RalphState)

    g.add_node("planner", wrap_node("planner", planner_node))
    g.add_node("executor", wrap_node("executor", executor_node))
    g.add_node("evaluator", wrap_node("evaluator", evaluator_node))
    g.add_node("consultant", wrap_node("consultant", cloud_consultant_node))

    g.set_entry_point("planner")
    g.add_edge("planner", "executor")
    g.add_edge("executor", "evaluator")
    
    # After consultation, the run naturally ends for human review
    g.add_edge("consultant", END)

    g.add_conditional_edges(
        "evaluator",
        meta_route_decision,
        {
            "executor": "executor",
            "consultant": "consultant",
            END: END,
        },
    )

    return g.compile(checkpointer=checkpointer)

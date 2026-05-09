"""Dynamic topology loader for RALPH.
Loads graph structure from graph.json in the task directory.
"""
import json
import importlib
import sys
from pathlib import Path
from langgraph.graph import StateGraph, END

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from state import RalphState
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
    task_dir = Path(__file__).parent
    graph_file = task_dir / "graph.json"
    
    if not graph_file.exists():
        raise FileNotFoundError(f"No graph.json found in {task_dir}")
        
    data = json.loads(graph_file.read_text(encoding="utf-8"))
    g = StateGraph(RalphState)
    
    # 1. Add Nodes
    for node_data in data.get("nodes", []):
        node_id = node_data["id"]
        module_path = node_data["module"]
        func_name = node_data["func"]
        
        if module_path == "topology":
            # Local node in this file
            node_func = getattr(sys.modules[__name__], func_name)
        else:
            module = importlib.import_module(module_path)
            node_func = getattr(module, func_name)
            
        g.add_node(node_id, wrap_node(node_id, node_func))
        
    # 2. Add Edges
    for edge in data.get("edges", []):
        g.add_edge(edge["source"], edge["target"])
        
    # 3. Add Conditional Edges
    for c_edge in data.get("conditional_edges", []):
        # Mapping needs to handle END sentinel
        mapping = {k: (END if v == "__end__" else v) for k, v in c_edge["mapping"].items()}
        
        # Condition func (currently only route_decision supported globally)
        cond_func = route_decision # could be dynamic via importlib too
        
        g.add_conditional_edges(c_edge["source"], cond_func, mapping)
        
    # 4. Set Entry Point
    g.set_entry_point(data["entry_point"])
    
    return g.compile(checkpointer=checkpointer)

"""D4: LangGraph minimal graph — no LLM calls, pure Python nodes.
Checks: import, compile, stream, correct output.
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

def check(label, fn):
    try:
        result = fn()
        print(f"  PASS  {label}")
        return True, result
    except Exception as e:
        print(f"  FAIL  {label}")
        print(f"        {type(e).__name__}: {e}")
        return False, None

def can_import_langgraph():
    from langgraph.graph import StateGraph, END  # noqa: F401

def graph_compiles():
    from langgraph.graph import StateGraph, END
    from typing import TypedDict

    class S(TypedDict):
        value: int

    def inc(state: S) -> dict:
        return {"value": state["value"] + 1}

    def double(state: S) -> dict:
        return {"value": state["value"] * 2}

    g = StateGraph(S)
    g.add_node("inc", inc)
    g.add_node("double", double)
    g.set_entry_point("inc")
    g.add_edge("inc", "double")
    g.add_edge("double", END)
    compiled = g.compile()
    return compiled

def graph_streams_correct_output(compiled):
    steps = list(compiled.stream({"value": 3}, stream_mode="updates"))
    # inc: 3+1=4, double: 4*2=8
    final_value = steps[-1].get("double", {}).get("value")
    assert final_value == 8, f"expected 8, got {final_value}  steps={steps}"
    print(f"          streamed {len(steps)} nodes, final value = {final_value}")

if __name__ == "__main__":
    print(f"\n[D4] LangGraph")
    r1, _ = check("langgraph importable", can_import_langgraph)
    r2, compiled = check("StateGraph compiles with 2 nodes", graph_compiles)
    if r2 and compiled:
        r3, _ = check("graph streams correct output (3 -> inc -> double = 8)",
                      lambda: graph_streams_correct_output(compiled))
    else:
        r3 = False
    ok = r1 and r2 and r3
    print(f"\n  {'ALL PASS' if ok else 'FAILED'}\n")
    sys.exit(0 if ok else 1)

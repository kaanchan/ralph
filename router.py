"""LiteLLM routing — single call site for all LLM requests in the loop."""
import os
import litellm
from config import LOCAL_MODEL, CLOUD_MODEL, OLLAMA_BASE_URL, ESCALATE_AFTER
from state import RalphState

litellm.set_verbose = False


def select_model(state: RalphState) -> str:
    """Deterministic routing: local by default, cloud after repeated failures."""
    if state["escalated"]:
        return CLOUD_MODEL
    if state["iterations"] >= ESCALATE_AFTER:
        return CLOUD_MODEL
    return LOCAL_MODEL


def llm_call(prompt: str, model: str, system: str = "") -> str:
    """Unified LLM call through LiteLLM — falls back to local if cloud fails."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    def _call(m: str) -> str:
        kwargs = dict(model=m, messages=messages, temperature=0.2)
        if m.startswith("ollama/"):
            kwargs["api_base"] = OLLAMA_BASE_URL
        response = litellm.completion(**kwargs)
        return response.choices[0].message.content.strip()

    try:
        return _call(model)
    except Exception as e:
        if model != LOCAL_MODEL:
            print(f"  [router] cloud call failed ({e.__class__.__name__}), falling back to local")
            return _call(LOCAL_MODEL)
        raise


def route_decision(state: RalphState) -> str:
    """
    Conditional edge function — LangGraph calls this after evaluator_node
    to decide which node to visit next. Returns a node name or END.
    """
    from langgraph.graph import END

    if state["done"] or state["score"] >= 0.75:
        return END

    if state["iterations"] >= 5:
        return END  # hard stop regardless of score

    if not state["escalated"] and state["iterations"] >= ESCALATE_AFTER:
        return "escalate"  # triggers escalation path

    return "executor"  # retry with same or cloud model

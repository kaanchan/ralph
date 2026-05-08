"""LiteLLM routing — single call site for all LLM requests in the loop.

Hardened: every llm_call has a hard timeout. On timeout we don't raise — we
return TIMEOUT_SENTINEL so the evaluator can score 0 and the loop can
escalate, instead of crashing the whole graph.
"""
import litellm
from langgraph.graph import END
from config import (
    LOCAL_MODEL, CLOUD_MODEL, OLLAMA_API_BASE, ESCALATE_AFTER,
    LLM_TIMEOUT_SHORT, MAX_CONSECUTIVE_TIMEOUTS, TIMEOUT_SENTINEL,
    RALPH_VERBOSE,
)
from runlog import log, loud_timeout
from state import RalphState

litellm.set_verbose = bool(RALPH_VERBOSE)


def select_model(state: RalphState) -> str:
    """Deterministic routing: local by default, cloud after repeated failures."""
    if state["escalated"]:
        return CLOUD_MODEL
    if state["iterations"] >= ESCALATE_AFTER:
        return CLOUD_MODEL
    return LOCAL_MODEL


def llm_call(prompt: str, model: str, system: str = "") -> str:
    """Unified LLM call through LiteLLM. Returns TIMEOUT_SENTINEL on timeout
    (never raises Timeout to the caller — caller routes on the sentinel)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    def _call(m: str) -> str:
        log(f"llm_call -> {m} (timeout={LLM_TIMEOUT_SHORT}s, prompt={len(prompt)} chars)")
        kwargs = dict(
            model=m, messages=messages, temperature=0.2,
            timeout=LLM_TIMEOUT_SHORT, num_retries=0,
        )
        if m.startswith("ollama/"):
            kwargs["api_base"] = OLLAMA_API_BASE
        response = litellm.completion(**kwargs)
        out = response.choices[0].message.content.strip()
        log(f"llm_call <- {m} ({len(out)} chars)")
        return out

    try:
        return _call(model)
    except litellm.Timeout:
        loud_timeout(f"llm_call model={model}", LLM_TIMEOUT_SHORT)
        return TIMEOUT_SENTINEL
    except Exception as e:
        # Cloud failure → fall back to local; local failure → bubble up
        if model != LOCAL_MODEL:
            log(f"llm_call: cloud {model} failed ({e.__class__.__name__}), trying local")
            try:
                return _call(LOCAL_MODEL)
            except litellm.Timeout:
                loud_timeout(f"llm_call fallback model={LOCAL_MODEL}", LLM_TIMEOUT_SHORT)
                return TIMEOUT_SENTINEL
        log(f"llm_call: {model} raised {e.__class__.__name__}: {e}")
        raise


def route_decision(state: RalphState) -> str:
    """Conditional edge — decides what runs next after the evaluator.

    Hard-fail path: MAX_CONSECUTIVE_TIMEOUTS in a row means something is
    structurally wrong (Ollama down, model unloaded, network broken). Stop
    looping and return so the user sees the failure instead of burning quota.
    """
    if state.get("timeout_count", 0) >= MAX_CONSECUTIVE_TIMEOUTS:
        log(f"route: HARD-FAIL — {state['timeout_count']} consecutive timeouts")
        return END

    if state["done"] or state["score"] >= 0.75:
        return END

    if state["iterations"] >= 5:
        return END

    if not state["escalated"] and state["iterations"] >= ESCALATE_AFTER:
        return "escalate"

    return "executor"

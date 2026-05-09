"""LiteLLM routing — single call site for all LLM requests in the loop.

Hardened: every llm_call has a hard timeout. On timeout we don't raise — we
return TIMEOUT_SENTINEL so the evaluator can score 0 and the loop can
escalate, instead of crashing the whole graph.
"""
import time
import litellm
from langgraph.graph import END
from config import (
    LOCAL_MODEL, CLOUD_MODEL, OLLAMA_API_BASE, ESCALATE_AFTER,
    LLM_TIMEOUT_SHORT, MAX_CONSECUTIVE_TIMEOUTS, TIMEOUT_SENTINEL,
    RALPH_VERBOSE,
)
from runlog import log, loud_timeout
from state import RalphState
from telemetry import tracer

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
    log(f"llm -> {model} (timeout={LLM_TIMEOUT_SHORT}s)")
    t0 = time.time()

    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        timeout=LLM_TIMEOUT_SHORT,
        num_retries=0,
    )
    if model.startswith("ollama/"):
        kwargs["api_base"] = OLLAMA_API_BASE
        
    flags = kwargs.copy()
    flags.pop("messages", None)
    span_id = tracer.start_tool("llm", f"litellm [{model}]", f"{system}\n\n{prompt}", flags=flags)

    try:
        response = litellm.completion(**kwargs)
        out = response.choices[0].message.content.strip()
        usage = dict(response.usage) if hasattr(response, "usage") and response.usage else {}
        tracer.end_tool(span_id, "success", out, metrics=usage)
        log(f"llm <- {model} finished in {time.time()-t0:.1f}s ({len(out)} chars)")
        return out

    except (litellm.Timeout, litellm.exceptions.APIConnectionError) as e:
        tracer.end_tool(span_id, "failed", str(e))
        loud_timeout(f"llm_call model={model}", LLM_TIMEOUT_SHORT)
        return TIMEOUT_SENTINEL

    except Exception as e:
        tracer.end_tool(span_id, "failed", str(e))
        # Any model failure → return sentinel so the loop can route/escalate
        log(f"llm_call: {model} raised {e.__class__.__name__}: {e}")
        if model != LOCAL_MODEL:
            log(f"llm_call: cloud {model} failed, returning sentinel")
        return TIMEOUT_SENTINEL


def route_decision(state: RalphState) -> str:
    """Conditional edge — decides what runs next after the evaluator.

    Hard-fail path: MAX_CONSECUTIVE_TIMEOUTS in a row means something is
    structurally wrong (Ollama down, model unloaded, network broken). Stop
    looping and return so the user sees the failure instead of burning quota.
    """
    if state.get("timeout_count", 0) >= MAX_CONSECUTIVE_TIMEOUTS:
        if not state.get("escalated"):
            log(f"route: Circuit Breaker — {state['timeout_count']} timeouts -> escalating to cloud")
            return "escalate"
        else:
            log(f"route: HARD-FAIL — {state['timeout_count']} consecutive timeouts on cloud model")
            return END

    if state["done"] or state["score"] >= 0.75:
        return END

    if state["iterations"] >= 5:
        return END

    if not state["escalated"] and state["iterations"] >= ESCALATE_AFTER:
        return "escalate"

    return "executor"

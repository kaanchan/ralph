# Pending Task — ralph

## Current State (verified 2026-09-07)
- Branch: master (swarm work lands on `swarm/20260907-2`)
- The 2026-05-06 timeout/observability hardening checklist that used to live in this
  file is DONE — verified line-by-line against current source, not assumed:
  - `config.py`: OLLAMA_API_BASE/OLLAMA_BASE_URL alias, all timeouts env-overridable
    (`RALPH_TIMEOUT_LLM/AIDER/GIT`, `RALPH_SILENT_WARN`), `TIMEOUT_SENTINEL`.
  - `router.py::llm_call()`: hard timeout + sentinel on Timeout/APIConnectionError.
  - `router.py::route_decision()`: circuit breaker on `MAX_CONSECUTIVE_TIMEOUTS`.
  - `executor.py`: Popen + reader thread, `SILENT_WARN_AFTER` watchdog, hard kill at
    `AIDER_TIMEOUT`, `timeout_count` threaded through `state.py`.
  - `evaluator.py`: detects `TIMEOUT_SENTINEL`, scores 0.
  - No code work needed here — do not re-do it.

## Active thread: issue #2 (local model / Aider diagnosis), blocks #1

See https://github.com/kaanchan/ralph/issues/2 and the triage in
https://github.com/kaanchan/ralph/issues/3 for full context.

- [x] Handoff doc (`docs/Claude_Handoff.md` §8 Step 2 — drop plan from test prompt):
      already applied in `prompts/test_solution.txt` + `executor.py::run_aider()`.
- [x] §8 Step 3 (wait for Ollama idle after a timeout): `executor.py::_wait_for_ollama()`
      exists and is called from `executor_node()` on timeout.
- [x] §8 Step 1 (capture raw streaming output for short vs long plan): executed
      2026-09-07 via new `diagnostics/d8_stream_capture.py`. Result: no reasoning-mode
      preamble at either plan length once `num_ctx` is capped (8192) — see
      `docs/Claude_Handoff.md` §8a Addendum for the full writeup and hypothesis.
- [ ] **Next unit**: a live end-to-end run — `python diagnostics/d6_ralph_loop.py` or
      `python main.py --repo ../ralph-test-target "<simple task>"` — to check issue
      #2's actual success criterion (no cloud escalation) against CURRENT code.
      Nobody has run this since the fixes above landed; the last recorded run
      (`logs/traces/run_20260509_004143_c8b526`, cited in issue #3) predates them and
      still shows the old failure mode, so it is not evidence about current code.
      Budget ~3 min wall-clock per the handoff doc; follow the gpu-guard skill
      (SERIAL, precheck, liveness deadline) since it drives the local model directly.

## Known Gaps / Future Work (deferred, unchanged from prior sessions)
- Sandboxing: executor runs code on host — add WSL/Docker isolation later
- Evaluator uses regex on test output, not LLM — fine for MVP
- Get fresh Gemini API key (current one quota-exhausted as of 2026-05)
- Get fresh LangSmith API key
- Test `langgraph dev` for LangGraph Studio web visualization
- Issue #1 (observability/TV-mode) is explicitly blocked on #2 being stable — don't
  start it until the item above lands with a real passing run.

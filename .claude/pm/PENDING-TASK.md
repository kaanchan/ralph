# Pending Task — ralph

## Current State
- Branch: main
- Phase: Hardening timeouts + observability after Aider hang debug session
- Aider hang root cause: post-edit auto-commit LLM call on new files (no HEAD baseline)
- Fix already in place: executor.py uses --no-auto-commits + --no-dirty-commits + script-managed commits

## In Progress — Timeout & Observability Hardening
User signed off on the plan 2026-05-06. Executing now.

### Bug to fix in same pass
- [ ] `executor.py:16` imports `OLLAMA_API_BASE` but `config.py:12` defines `OLLAMA_BASE_URL` → ImportError on first run.
      Fix: rename in config.py to `OLLAMA_API_BASE`, update router.py import to match.

### Tiered timeouts (env-overridable)
- [ ] `config.py`: add `LLM_TIMEOUT_SHORT=30`, `AIDER_TIMEOUT=90`, `GIT_TIMEOUT=10`, `SILENT_WARN_AFTER=15`, `RALPH_LOG_PATH`
- [ ] All read from env: `RALPH_TIMEOUT_LLM`, `RALPH_TIMEOUT_AIDER`, `RALPH_TIMEOUT_GIT`, `RALPH_SILENT_WARN`

### LLM call hardening (router.py)
- [ ] `llm_call()` add `timeout=LLM_TIMEOUT_SHORT` to litellm.completion
- [ ] Catch litellm Timeout/APIConnectionError → log loudly + return sentinel `"<<RALPH_TIMEOUT>>"`
- [ ] Loud log includes ollama /api/ps state at moment of timeout

### Executor hardening (executor.py)
- [ ] Switch `subprocess.run(capture_output=True)` → Popen + reader thread + 0.5s poll
- [ ] Stream lines live to console + ralph_run.log
- [ ] Watchdog at SILENT_WARN_AFTER seconds → emit warning (still running)
- [ ] Hard kill at AIDER_TIMEOUT
- [ ] On timeout: return empty stdout + sentinel in stderr; do NOT raise
- [ ] _git timeout 15 → 10

### State + routing (state.py, evaluator.py, router.py)
- [ ] state.py: add `timeout_count: int` to RalphState
- [ ] evaluator.py: detect timeout sentinel → score 0.05 + reason "executor timed out"
- [ ] route_decision: 2 consecutive timeouts → END (hard fail with clear message), not loop forever

### Observability (main.py)
- [ ] Open ralph_run.log; mirror all node output to it
- [ ] Document `Get-Content -Wait ralph_run.log` for live tailing

## Pending Verification (after this hardening lands)
- [ ] python diagnostics\d3_aider.py → Variant D passes
- [ ] python diagnostics\run_all.py --fast → D1–D5 all pass
- [ ] python main.py --repo ../ralph-test-target "write a function that adds two numbers and a test" → end-to-end success
- [ ] Test timeout path: temporarily set `RALPH_TIMEOUT_LLM=2` and confirm sentinel + escalation work

## Known Gaps / Future Work (deferred)
- Sandboxing: executor runs code on host — add WSL/Docker isolation later
- Evaluator uses regex on test output, not LLM — fine for MVP
- Get fresh Gemini API key (current one quota-exhausted)
- Get fresh LangSmith API key
- Test `langgraph dev` for LangGraph Studio web visualization

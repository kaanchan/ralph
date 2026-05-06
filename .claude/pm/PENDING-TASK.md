# Pending Task — ralph

## Current State
- Branch: main
- Phase: Initial scaffold complete, not yet tested end-to-end

## What's Built
- [x] config.py — central config (models, thresholds, paths)
- [x] state.py — RalphState TypedDict
- [x] router.py — LiteLLM routing + model selection + conditional edge fn
- [x] executor.py — Aider subprocess wrapper + code runner
- [x] evaluator.py — LLM-based scorer returning 0.0–1.0
- [x] graph.py — LangGraph StateGraph (planner→executor→evaluator→router)
- [x] main.py — CLI entry point with Rich output
- [x] memory.py — JSON run persistence

## Immediate Next Steps
- [ ] Get Gemini API key from https://aistudio.google.com/app/apikey
- [ ] Copy .env.example → .env, add GEMINI_API_KEY
- [ ] First smoke test: python main.py "write hello world"
- [ ] Confirm local Ollama path works end-to-end
- [ ] Test cloud escalation path

## Known Gaps / Future Work
- Sandboxing: executor runs code on host — add WSL or Docker isolation later
- Aider --no-git flag: works for MVP but loses commit tracking
- Evaluator uses same LLM being evaluated — could bias scores; add heuristic fallback
- LangGraph streaming: currently blocking invoke(), add stream() for live output

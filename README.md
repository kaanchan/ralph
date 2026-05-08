# RALPH (Recursive Agentic Local Python Hacker)

RALPH is a local-first recursive coding agent. Given a task description and a target git repo, it iteratively plans, executes, evaluates, and loops. It optimizes for cost by using free local 14B models (like `qwen25-coder-14b`) via a direct Ollama API call for code generation, and gracefully falls back to a highly capable cloud model (Gemini) using Aider when local attempts fail.

## 📁 Project Structure

The project has been carefully restructured to isolate concerns and enforce a maintainable architecture.

- **`.env`**: Contains your API keys and environment variables (ignored by git).
- **`.gitignore`**: Defines files and directories to be excluded from version control.
- **`langgraph.json`**: Configuration file for LangGraph Studio/CLI.
- **`requirements.txt`**: Python dependencies for the project.

### Directories

- **`src/`**: The core application logic.
  - `main.py`: CLI entry point.
  - `graph.py`: LangGraph definition orchestrating the loop.
  - `executor.py`: Writes code files, handling the local (Ollama) vs cloud (Aider) split.
  - `hardware.py`: Dynamic hardware profiler to query free VRAM via `nvidia-smi`.
  - `model_registry.py`: Registry defining model capabilities and VRAM baselines.
  - `planner.py`, `router.py`, `evaluator.py`, `state.py`: Core LangGraph node operations.
  - `config.py`: Centralized configuration.
  - `runlog.py`: Runtime logging logic.
- **`tests/`**: Unit and integration tests for the individual components.
- **`diagnostics/`**: A layered smoke test suite (`run_all.py`, `d1_ollama.py`, etc.) for validating the environment and model capabilities before executing a heavy run.
- **`docs/`**: Documentation, including architecture research and handoff documents.
- **`prompts/`**: Extracted string templates for system prompts.
- **`plans/`**: Versioned implementation plans generated during agentic planning sessions.
- **`logs/`**: Dedicated directory for application runtime logs (`ralph_run.log`).
- **`memory/`**: Directory where the LangGraph agent saves its run history as JSON.
- **`workspace/`**: Working directory for transient operations and Aider logs.

## 🚀 Current Status

RALPH currently has a fully stable execution loop. The core issues of Ollama socket hanging due to VRAM exhaustion have been resolved by implementing:
1. **Dynamic Profiling**: `src/hardware.py` dynamically probes VRAM to calculate maximum Context Window limits before calling Ollama.
2. **Execution Decoupling**: The implementation plan is no longer concatenated to the test generation prompt, drastically reducing context bloat and avoiding timeouts.
3. **Active Readiness Probing**: `executor.py` actively polls the Ollama server after a timeout or failure to ensure VRAM is completely clear before routing the next node.

### Running RALPH

Ensure your `.env` is properly populated and dependencies are installed in your `.venv`. 

```bash
python src/main.py --repo ../ralph-test-target "Your task description here"
```

# RALPH Refactoring & Capability Profiling Plan

This plan addresses your requests to restructure the project, implement a hardware-aware model registry, save the research notes in a Q&A format, and clarify where the generated code lives.

## 1. Where are `solution.py` and `test_solution.py`?
They are intentionally generated **outside** of this repository to prevent RALPH from accidentally overwriting its own code! If you look at the command run in `HANDOFF.md`, it uses `python main.py --repo ../ralph-test-target`. 
You will find those files located at `C:\Users\kaanchan\Projects\AI\ralph-test-target\`.

## User Review Required

Please review the proposed project restructure and new components. 

> [!IMPORTANT]
> Since this involves moving almost every Python file into a `src/` directory, you will need to restart any active terminals running `main.py` after this refactor. Is this structure acceptable?

## Proposed Changes

### 1. Document Creation
#### [NEW] `docs/QnA_Architecture_Research.md`
I will translate the previous research report into a clear Q&A format, detailing the specific questions you asked and the answers I found regarding LangGraph, Aider, and Ollama. I will place this in the new `docs/` folder. *(Note: I will also save this as an internal project KI as requested).*

### 2. Project Clean Up (Restructuring)
I will reorganize the root directory to adhere to standard Python project practices.

#### [MODIFY] Move source code to `src/`
- Move `config.py`, `evaluator.py`, `executor.py`, `graph.py`, `main.py`, `memory.py`, `router.py`, `runlog.py`, `state.py` into `src/`.
- Update all internal imports across these files.

#### [MODIFY] Move tests to `tests/`
- Move `test_gemini.py`, `test_langsmith.py`, `test_local.py` to a dedicated `tests/` directory.

#### [NEW] `prompts/` directory
- I will extract the hardcoded system prompts (like `_LOCAL_SYSTEM` and the Aider string prompts) from `executor.py` into template files in a `prompts/` directory for easier editing and versioning.

### 3. Hardware Profiler & Model Registry
To implement your excellent suggestion for dynamic configuration based on actual hardware, I will build two new modules:

#### [NEW] `src/hardware.py`
This module will execute `nvidia-smi` (which is standard on Windows with Nvidia GPUs like your RTX 3090) to query the **actual free VRAM** available on the system before a run.

#### [NEW] `src/model_registry.py`
A centralized dictionary (or JSON) defining the capabilities of the models. For example:
```python
MODELS = {
    "qwen25-coder-14b": {
        "supports_aider_diff": False,  # We know this model fails at diffs
        "base_vram_mb": 9500,          # Minimum VRAM to hold weights
        "system_prompt": "qwen_coder", # Points to the prompts/ folder
        "optimal_temperature": 0.1
    }
}
```

#### [MODIFY] `src/executor.py` (Integration)
Before calling Ollama, the executor will query `hardware.py` for `free_vram_mb` and look up the model in `model_registry.py`. It will dynamically calculate the maximum safe `num_ctx` (Context Window) to pass to the Ollama API, ensuring the model never spills to system RAM and never hangs again.

## Verification Plan
1. **Directory Integrity**: Run `python src/main.py --help` to ensure relative paths and imports resolve correctly.
2. **Hardware Profiling**: Run a standalone test of `hardware.py` to verify it correctly reads the RTX 3090's VRAM.
3. **End-to-End**: Run `python diagnostics/run_all.py` (which I will also update to point to `src/`) to ensure the entire refactored agent loop completes successfully.

---
## Completion Status
**Status:** IMPLEMENTED successfully on 2026-05-08.
- Hardware profiler works flawlessly.
- Project was restructured into `src/`, `tests/`, etc.
- Git tag `20260508_003156_gemini_plan` was applied.

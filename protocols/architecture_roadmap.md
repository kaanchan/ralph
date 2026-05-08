# RALPH Architecture & Evolution Roadmap

This document serves as the permanent scientific ledger for all brainstorming, proposed architectural pivots, and outstanding implementation plans. It ensures no idea is lost.

## 1. The "Task Pod" Architecture (Currently Executing)
**Status:** 🟢 Deployed (Engine Side) | 🟡 Pending (Dashboard Side)
- **Concept:** Shift from a monolithic global workspace to isolated `tasks/<task_id>/` directories.
- **Why:** Allows independent versioning of LangGraph configurations, Ollama parameters, and localized zoomable telemetry traces for reproducibility.
- **Dashboard Registry:** Tasks will write their path to a global `.ralph_registry.json`. The Streamlit dashboard will read this registry and populate a Dropdown menu, allowing the user to seamlessly switch between active/historical tasks. It will also allow manual absolute path entry.

## 2. The State Routing Matrix
**Status:** 🔴 Backlog (Pending Implementation)
- **Concept:** A scientific tracking matrix for handling graph execution states.
- **Why:** The agent currently blindly retries on timeouts or pytest failures. We need dynamic prompt injections.
- **Proposed Logic:**
  - `TIMEOUT (count=1)`: Route back to Executor with injected strict warning: *"CRITICAL: Previous run timed out. Output code only."*
  - `TIMEOUT (count>=2)`: Circuit breaker triggers Fast Escalation.
  - `TEST_FAILED`: Parse pytest traceback and inject directly into the next prompt.

## 3. The "Meta-Consultant" Cloud Node
**Status:** 🔴 Backlog (Pending Implementation)
- **Concept:** Repurposing the `escalate` node from a "code fixer" to an "AI Systems Architect Consultant".
- **Why:** Instead of burning cloud credits to write code when the local model fails, the cloud model analyzes the local model's failure trace and suggests parameter tweaks (e.g., `num_ctx`, `temperature`, stop tokens).
- **Execution:** Compiles a "Dossier of Failure" and asks Gemini: *"What would you suggest we tweak in our Ollama parameters so we don't reach your node next time?"*

## 4. Hardware-Aware Calibration Node
**Status:** 🔴 Backlog (Brainstormed)
- **Concept:** A node that runs before the planner to benchmark local TPS (tokens per second) and dynamically adjust the `LOCAL_MODEL_TIMEOUT` and context windows based on the host machine's capacity.

## 5. The Node Library Architecture
**Status:** 🟢 Executing
- **Concept:** Breaking down the monolithic script by moving all agent logic into a structured library: `src/nodes/<type>/<variant>.py`. 
- **Why:** This establishes a "plug-and-play" repository of agent behaviors (e.g., `default_planner`, `strict_ollama_executor`, `pytest_evaluator`, `cloud_consultant`).

## 6. Dynamic Task Topologies
**Status:** 🟢 Executing
- **Concept:** Removing the hardcoded `src/graph.py` and pushing the LangGraph topology logic into the Task Pods themselves (`tasks/<task>/topology.py`).
- **Why:** Allows each task to wire up its own custom graph by importing specific node variants from the `src/nodes/` library. Enables small, observable, custom graph setups on a per-task basis.

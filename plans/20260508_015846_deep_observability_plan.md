# Deep Observability Explorer Architecture

You are absolutely right—a status board is nice, but to debug and improve an agentic loop, you need an **X-Ray of the execution stack**. Every prompt, every timing, every tool output needs to be explorable.

Since you want to avoid black boxes and keep everything offline (no LangSmith), we need to build a custom **Telemetry Engine**.

## The Proposed Architecture

### 1. The Telemetry Engine (`src/telemetry.py`)
Instead of a flat `live_state.json`, we will implement a "Span-based" tracing system (similar to OpenTelemetry, but lightweight and JSON-native). 
- We will track a tree of "Spans". 
- The root span is the **Run**.
- Children of the Run are **Nodes** (Planner, Executor, Evaluator).
- Children of Nodes are **Tools** (LiteLLM, Ollama API, Pytest, Aider).
- Every Span records `start_time`, `end_time`, `duration`, `inputs` (the exact prompt or command), `outputs` (the raw string or traceback), and `status` (success/failure).
- This entire tree will be constantly dumped to `logs/trace_live.json`.

### 2. Instrumentation (The "Hooks")
We will inject this telemetry across the stack:
- **`src/main.py`**: Will manage the high-level Run and Node spans as the LangGraph loop ticks.
- **`src/executor.py` & `src/evaluator.py`**: Will wrap their internal subprocesses and API calls (Ollama, Pytest, Aider) in Tool spans, capturing their exact inputs and outputs and associating them with the currently active Node.

### 3. The Interactive Explorer (`src/dash_streamlit.py`)
While HTML/JS is great for a fixed TV layout, **Streamlit** is the absolute king of interactive data exploration in Python. I will completely rewrite the Streamlit dashboard to consume `trace_live.json` and render a deeply explorable, collapsible tree:
- **Top Level**: High-level metrics (Total Time, Iterations, Final Score).
- **The Timeline**: A chronological list of LangGraph Nodes executed.
- **The Expanders**: Clicking a Node (e.g., "Executor - 45s") expands it to reveal the internal tools used. Clicking a Tool (e.g., "Pytest - 2s") expands to show the exact command ran and the raw `stdout` traceback. Clicking "Ollama - 42s" reveals the exact raw system prompt, user prompt, and verbatim model response.

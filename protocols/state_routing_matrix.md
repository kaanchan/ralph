# The State Routing Matrix

This ledger tracks how the LangGraph Router and Executor dynamically handle execution states.

| Graph State Trigger | Router Decision | Executor Dynamic Prompt Injection | Status / Efficacy |
| :--- | :--- | :--- | :--- |
| **`TIMEOUT`** (1st Offense) | Route back to Executor (Retry) | *"CRITICAL: Your previous generation timed out (likely infinite loop). Provide ONLY the raw code."* | 🟢 Active |
| **`TIMEOUT`** (≥2 Offenses) | **Fast Escalate** to Cloud | *N/A (Cloud model takes over)* | 🟢 Active |
| **`TEST_FAILED`** (Score < 1) | Route back to Executor (Retry) | Inject exact Pytest Traceback: *"CRITICAL: Your previous code failed with: [TRACEBACK]. Fix this bug."* | 🔴 Pending |
| **`EVAL_ERROR`** (Parse fail) | Route back to Executor (Retry) | *"CRITICAL: The evaluator could not parse your code blocks. Use strict markdown."* | 🔴 Pending |
| **`NO_EDIT`** (Code extractor finds no code block) | Route back to Executor (Retry) | *"CRITICAL: Your response contained no recognizable code block. Wrap your code in ```python ... ``` fences."* | 🔴 Discovered — Pending |
| **`SUCCESS`** (Score == 1) | Route to `END` | *N/A* | 🟢 Active |

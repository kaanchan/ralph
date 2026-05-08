# Offline Observability & TV-Mode Visualization Layer (Issue #1)

This plan implements a terminal-native, full-screen "TV-mode" dashboard using the `rich` library. This satisfies Issue #1 by providing real-time offline observability of the LangGraph execution loop without requiring a cloud service like LangSmith.

## Proposed Changes

### [NEW] `src/dashboard.py`
Create a `RalphDashboard` class that manages a full-screen `rich.live.Live` rendering context.
- **Layout Construction**: Splits the terminal screen into a beautifully styled grid:
  - **Header Panel**: Displays the current task, target repo, and current Loop Iteration.
  - **Left Panel (State)**: Displays the current Implementation Plan and the last Test Output.
  - **Right Panel (Live Logs)**: Acts as a tailing log viewer, immediately showing Ollama heartbeats, node transitions, and model timeouts.
- **Methods**: `update_node(node_name, output)`, `update_logs(entries)` to safely mutate the UI state.

### [MODIFY] `src/main.py`
- Replace the current linear `console.print()` loop.
- Wrap the `graph.stream(...)` generator inside a `with Live(...)` context.
- At each step of the LangGraph loop, feed the state updates to the dashboard instead of scrolling the terminal down.

### [MODIFY] `src/runlog.py`
- Enhance the `log()` function. Add a callback registry so that when `log()` is called, it can broadcast the string to the active Dashboard instance, allowing real-time UI updates for long-running subprocesses.

## Verification Plan
1. **Automated Diagnostics**: Run `python diagnostics/run_all.py` to ensure the new `runlog.py` logic doesn't break headless diagnostic execution.
2. **Visual Smoke Test**: Run `python src/main.py --repo ../ralph-test-target "write a python function to check if a string is a palindrome"` and visually verify that the full-screen terminal UI launches, renders the panes correctly, and streams logs in real-time.

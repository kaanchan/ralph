# Project Standards & Protocols

To maintain a robust, growing memory of architectural decisions, execution loops, and observability layers, the following protocol applies to all generated artifacts:

## 1. Plan Management
- All Implementation Plans MUST be saved to the `plans/` directory.
- The naming convention is `<YYYYMMDD_HHMMSS>_<plan_name>.md`.
- Completed plans should be appended with a "Completion Status" section outlining the final outcome.

## 2. Knowledge Base (Q&A)
- Any philosophical, architectural, or framework-related inquiries must be documented in `docs/dev_qa/`.
- The naming convention is `<YYYYMMDD_HHMMSS>_<topic>.md`.
- This ensures that future developers (or agents) understand *why* a decision was made (e.g., bypassing Aider for local models, or using Custom Telemetry over OpenTelemetry).

## 3. Observability Outputs
- All real-time telemetry traces are stored in `logs/trace_live.json`.
- Internal debug logging (the raw black-box outputs) is routed to `logs/tools_debug.log`.
- `logs/` serves as the ephemeral visualization source, whereas `memory/` serves as the permanent LangGraph state store.

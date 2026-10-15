"""Regression test for issue #2 (docs/Claude_Handoff.md section 8, Step 2).

A long planner output prepended to the test-writing prompt pushed the local
model into a reasoning-mode preamble instead of code. Fix: only the
solution.py prompt carries the plan; the test_solution.py prompt never does.
Offline: _write_file is stubbed, no Ollama or Aider is touched.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import executor  # noqa: E402

PLAN = "PLAN-SENTINEL: step 1 do X, step 2 do Y"
TASK = "write a fibonacci function"


def test_plan_goes_to_solution_prompt_only(tmp_path, monkeypatch):
    prompts = {}

    def fake_write_file(message, model, target, repo_dir, label):
        prompts[label] = message
        return "", ""

    monkeypatch.setattr(executor, "_write_file", fake_write_file)
    monkeypatch.setattr(executor, "AIDER_LOG_PATH", tmp_path / "aider_last.log")
    monkeypatch.setattr(executor, "log", lambda *a, **k: None)

    executor.run_aider(TASK, PLAN, "ollama/qwen25-coder-14b", tmp_path)

    assert PLAN in prompts["solution.py"]
    assert TASK in prompts["solution.py"]
    assert PLAN not in prompts["test_solution.py"]
    assert TASK in prompts["test_solution.py"]

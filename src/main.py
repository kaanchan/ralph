"""
RALPH -- Recursive Agent Loop with Planner/Handler

Usage:
    python main.py --repo C:/path/to/your/repo "add a hello world function"
    python main.py --history
"""
import argparse
import os
import sys
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
# Removed static graph import. Topology is loaded dynamically per Task Pod.
from memory import save_run, load_runs
from state import RalphState
from runlog import reset_log
from state_exporter import export_state
from telemetry import tracer
from langgraph.graph import END
from config import RALPH_LOG_PATH, AIDER_LOG_PATH, MAX_CONSECUTIVE_TIMEOUTS

# legacy_windows=False disables the cp1252 Windows renderer; safe=True
# means unknown chars are replaced instead of crashing.
# Use Windows Terminal for best results -- it's UTF-8 native.
console = Console(force_terminal=True, legacy_windows=False, highlight=False, safe_box=True)


def initial_state(task: str, repo_dir: str) -> RalphState:
    return RalphState(
        task=task,
        repo_dir=repo_dir,
        plan="",
        code="",
        test_output="",
        score=0.0,
        iterations=0,
        model_used="",
        escalated=False,
        done=False,
        timeout_count=0,
        consultant_advice="",
        log=[],
    )


def print_summary(state: RalphState) -> None:
    success = state["done"] or state["score"] >= 0.75
    timed_out = state.get("timeout_count", 0) >= MAX_CONSECUTIVE_TIMEOUTS

    if timed_out:
        console.print(Panel(
            f"[bold red]HARD-FAIL[/bold red] — {state['timeout_count']} consecutive timeouts.\n"
            f"Likely causes: Ollama down, model unloaded, or local model can't handle the prompt shape.\n"
            f"Check: ollama list  /  ollama ps  /  inspect {RALPH_LOG_PATH}",
            border_style="red", title="Run aborted",
        ))

    console.print()
    table = Table(title="RALPH Run Summary", show_lines=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Task", state["task"])
    table.add_row("Iterations", str(state["iterations"]))
    table.add_row("Final score", f"{state['score']:.2f}")
    table.add_row("Model used", state["model_used"])
    table.add_row("Escalated", "yes" if state["escalated"] else "no")
    table.add_row("Cost tier", "cloud" if state["escalated"] else "local")
    if timed_out:
        table.add_row("Success", "[red]TIMEOUT[/red]")
    else:
        table.add_row("Success", "PASS" if success else "FAIL")
    console.print(table)

    console.print("\n[bold]Decision log:[/bold]")
    for entry in state["log"]:
        console.print(f"  {entry}")

    if state["code"]:
        console.print(Panel(state["code"], title="Generated code", border_style="green"))
    if state["test_output"]:
        console.print(Panel(state["test_output"], title="Test output", border_style="yellow"))


def print_history() -> None:
    runs = load_runs()
    if not runs:
        console.print("[yellow]No run history found.[/yellow]")
        return
    table = Table(title=f"Run history ({len(runs)} runs)")
    table.add_column("Timestamp")
    table.add_column("Task")
    table.add_column("Iters")
    table.add_column("Score")
    table.add_column("Model")
    table.add_column("Cloud?")
    for r in runs:
        table.add_row(
            r["timestamp"],
            r["task"][:50] + ("..." if len(r["task"]) > 50 else ""),
            str(r["iterations"]),
            f"{r['final_score']:.2f}",
            r["model_used"],
            "yes" if r["escalated"] else "no",
        )
    console.print(table)


def main() -> None:
    p = argparse.ArgumentParser(description="RALPH -- local-first coding agent loop")
    p.add_argument("command", choices=["run", "history"], help="Command: 'run' to start a task, 'history' for global run log")
    p.add_argument("task_dir", nargs="?", help="Path to the isolated task directory (e.g. tasks/001_fibonacci)")
    args = p.parse_args()

    if args.command == "history":
        print_history()
        return

    if not args.task_dir:
        console.print("[red]Error:[/red] A task directory is required for the 'run' command.")
        console.print("Example: python src/main.py run tasks/001_fibonacci")
        sys.exit(1)

    task_dir = Path(args.task_dir).resolve()
    
    # 1. Re-route config paths
    from config import set_task_directory, ROOT
    set_task_directory(str(task_dir))
    
    # Reload config variables after re-routing
    from config import RALPH_LOG_PATH, AIDER_LOG_PATH
    
    # 1.5 Register Task for Streamlit Dashboard
    import json
    import time
    registry_file = ROOT / ".ralph_registry.json"
    registry = []
    if registry_file.exists():
        try:
            registry = json.loads(registry_file.read_text())
        except Exception:
            pass
    
    # Prepend this task to the registry
    registry = [r for r in registry if r.get("task_dir") != str(task_dir)]
    registry.insert(0, {"task_dir": str(task_dir), "name": task_dir.name, "timestamp": time.time()})
    registry_file.write_text(json.dumps(registry[:20], indent=2))  # keep last 20

    # 1.6 Redirect telemetry tracer to this Task Pod
    tracer.redirect(task_dir / "traces")

    # 2. Extract Goal from task.json
    task_file = task_dir / "task.json"
    if task_file.exists():
        task_data = json.loads(task_file.read_text())
        task_prompt = task_data.get("goal", "Execute task")
    else:
        task_prompt = "Execute task in directory"
        task_dir.mkdir(parents=True, exist_ok=True)
        task_file.write_text(json.dumps({"goal": task_prompt}, indent=2))

    repo_dir = str(task_dir / "src")
    reset_log()
    console.print(Panel(
        f"[bold]Task Pod:[/bold] {task_dir.name}\n"
        f"[dim]Goal:[/dim] {task_prompt}\n"
        f"[dim]Code Dir:[/dim] {repo_dir}\n"
        f"[dim]Run log:[/dim]   {RALPH_LOG_PATH}\n"
        f"[dim]Aider log:[/dim] {AIDER_LOG_PATH}\n"
        f"[dim]Tail:[/dim]      Get-Content -Wait \"{RALPH_LOG_PATH}\"",
        border_style="blue",
    ))
    console.print("[dim]Streaming node-by-node output below...[/dim]\n")

    # 3. Setup SQLite Checkpointer
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    
    db_path = task_dir / "checkpoints.sqlite"
    
    # 4. Load Dynamic Topology
    import importlib.util
    topology_file = task_dir / "topology.py"
    if not topology_file.exists():
        console.print(f"[red]Error:[/red] No topology.py found in {task_dir}")
        sys.exit(1)
        
    spec = importlib.util.spec_from_file_location("task_topology", topology_file)
    task_topology = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(task_topology)
    
    if not hasattr(task_topology, "build_graph"):
        console.print(f"[red]Error:[/red] topology.py must define a build_graph(checkpointer) function.")
        sys.exit(1)
        
    with sqlite3.connect(str(db_path), check_same_thread=False) as conn:
        memory = SqliteSaver(conn)
        graph = task_topology.build_graph(checkpointer=memory)
        
        # The thread_id allows resuming specific runs.
        # For a task pod, "1" represents the primary thread of execution.
        config = {"configurable": {"thread_id": "1"}}
        
        state = initial_state(task_prompt, repo_dir)
        export_state(state)
        tracer.set_task(task_prompt)

        try:
            for step in graph.stream(state, config=config, stream_mode="updates"):
                if not step:
                    continue
                if END in step:
                    from runlog import log
                    log("loop ended by router condition", also_console=True)
                    break

                final = {**state, **{k: v for d in step.values() for k, v in d.items()}}
                state = {**state, **final}
                
                tracer.update_run({
                    "iteration": state.get("iterations", 0),
                    "escalated": state.get("escalated", False)
                })
                
                export_state({
                    **state,
                    "status": f"Running {list(step.keys())[0]}..."
                })
                
                node_output = list(step.values())[0]
                if "log" in node_output and node_output["log"]:
                    console.print(f"   [dim]{node_output['log'][-1]}[/dim]")
                    
            tracer.end_run("success")
        except Exception as e:
            tracer.end_run(f"failed: {e}")
            raise

        print_summary(state)
        export_state({"status": "Finished."})
        path = save_run(state)
        console.print(f"\n[dim]Run saved -> {path}[/dim]")


if __name__ == "__main__":
    main()

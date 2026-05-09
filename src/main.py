"""
RALPH -- Recursive Agent Loop with Planner/Handler
"""
import argparse
import os
import sys
import sqlite3
import json
import time
import warnings
from pathlib import Path

# Filter common warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END

# RALPH Core Modules
from memory import save_run, load_runs
from state import RalphState
from runlog import reset_log
from state_exporter import export_state
from telemetry import tracer
from config import RALPH_LOG_PATH, AIDER_LOG_PATH, MAX_CONSECUTIVE_TIMEOUTS

console = Console(force_terminal=True, legacy_windows=False, highlight=False, safe_box=True)

def initial_state(task: str, repo_dir: str) -> RalphState:
    """Initialize the agentic state for a new task pod."""
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
    """Print a high-level summary of the mission results."""
    success = state["done"] or state["score"] >= 0.75
    console.print()
    table = Table(title="RALPH Run Summary", show_lines=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Task", state["task"])
    table.add_row("Iterations", str(state["iterations"]))
    table.add_row("Final score", f"{state['score']:.2f}")
    table.add_row("Success", "PASS" if success else "FAIL")
    console.print(table)

def main() -> None:
    try:
        p = argparse.ArgumentParser(description="RALPH -- local-first coding agent loop")
        p.add_argument("command", choices=["run", "history"], help="Command: 'run' to start a task, 'history' for global run log")
        p.add_argument("task_dir", nargs="?", help="Path to the isolated task directory")
        args = p.parse_args()

        if args.command == "history":
            runs = load_runs()
            if not runs:
                console.print("[yellow]No run history found.[/yellow]")
                return
            table = Table(title=f"Run history ({len(runs)} runs)")
            for r in runs:
                table.add_row(r.get("timestamp", "N/A"), r.get("task", "N/A")[:50], str(r.get("iterations", 0)), f"{r.get('final_score', 0):.2f}")
            console.print(table)
            return

        if not args.task_dir:
            console.print("[red]Error:[/red] A task directory is required for the 'run' command.")
            sys.exit(1)

        task_dir = Path(args.task_dir).resolve()
        
        # 1. Re-route config paths to the Task Pod
        from config import set_task_directory, ROOT
        set_task_directory(str(task_dir))
        
        # 1.5 Register Task for Streamlit Dashboard
        registry_file = ROOT / ".ralph_registry.json"
        registry = []
        if registry_file.exists():
            try:
                registry = json.loads(registry_file.read_text())
            except Exception:
                pass
        
        registry = [r for r in registry if r.get("task_dir") != str(task_dir)]
        registry.insert(0, {"task_dir": str(task_dir), "name": task_dir.name, "timestamp": time.time()})
        registry_file.write_text(json.dumps(registry[:20], indent=2))

        # 1.6 Redirect telemetry tracer
        tracer.redirect(task_dir / "traces")

        # 2. Extract Goal
        task_file = task_dir / "task.json"
        task_prompt = "Execute task"
        if task_file.exists():
            task_data = json.loads(task_file.read_text())
            task_prompt = task_data.get("goal", "Execute task")

        repo_dir = str(task_dir / "src")
        reset_log()
        console.print(Panel(
            f"[bold]Task Pod:[/bold] {task_dir.name}\n"
            f"[dim]Goal:[/dim] {task_prompt}",
            border_style="blue",
        ))

        # 3. Setup SQLite Checkpointer
        db_path = task_dir / "checkpoints.sqlite"
        
        # 4. Load Dynamic Topology
        import importlib.util
        topology_file = task_dir / "topology.py"
        spec = importlib.util.spec_from_file_location("task_topology", topology_file)
        task_topology = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = task_topology  # register so topology can find its own functions
        spec.loader.exec_module(task_topology)
        
        with sqlite3.connect(str(db_path), check_same_thread=False) as conn:
            memory = SqliteSaver(conn)
            graph = task_topology.build_graph(checkpointer=memory)
            config = {"configurable": {"thread_id": "1"}}
            
            state = initial_state(task_prompt, repo_dir)
            export_state(state)
            tracer.set_task(task_prompt)

            for step in graph.stream(state, config=config, stream_mode="updates"):
                # Check for control signals from dashboard
                signal_file = task_dir / "control.json"
                if signal_file.exists():
                    try:
                        control = json.loads(signal_file.read_text())
                        if control.get("command") == "pause":
                            signal_file.unlink(missing_ok=True)
                            break
                        elif control.get("command") == "abort":
                            signal_file.unlink(missing_ok=True)
                            sys.exit(0)
                    except Exception:
                        pass

                if not step or END in step:
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
            print_summary(state)
            export_state({"status": "Finished."})
            save_run(state)

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        console.print(Panel(f"[bold red]CRITICAL ERROR[/bold red]\n\n{error_msg}", title="RALPH Engine Crash", border_style="red"))
        # Save to crash log for Studio/Dashboard discovery
        if task_dir:
            try:
                (task_dir / "CRASH.log").write_text(error_msg, encoding="utf-8")
            except:
                pass
        if os.name == 'nt':
            input("\nPress Enter to close...")
        sys.exit(1)

if __name__ == "__main__":
    main()

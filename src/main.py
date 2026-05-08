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
# LangGraph's init calls warn_deprecated with stacklevel=4, which bypasses
# standard filter contexts. Temporarily no-op warnings.warn for the import.
# Set RALPH_VERBOSE_WARNINGS=1 to restore all warnings (useful for debugging
# what any layer of the stack is communicating).
if os.getenv("RALPH_VERBOSE_WARNINGS"):
    from graph import build_graph
else:
    _real_warn = warnings.warn
    warnings.warn = lambda *a, **kw: None
    try:
        from graph import build_graph
    finally:
        warnings.warn = _real_warn
from memory import save_run, load_runs
from state import RalphState
from runlog import reset_log
from state_exporter import export_state
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
    p.add_argument("task", nargs="?", help="Coding task to execute")
    p.add_argument("--repo", default=".", help="Path to the target git repo Aider will edit")
    p.add_argument("--history", action="store_true", help="Show run history")
    args = p.parse_args()

    if args.history:
        print_history()
        return

    if not args.task:
        p.print_help()
        sys.exit(1)

    repo_dir = str(Path(args.repo).resolve())
    reset_log()
    console.print(Panel(
        f"[bold]Task:[/bold] {args.task}\n[dim]Repo:[/dim] {repo_dir}\n"
        f"[dim]Run log:[/dim]   {RALPH_LOG_PATH}\n"
        f"[dim]Aider log:[/dim] {AIDER_LOG_PATH}\n"
        f"[dim]Tail:[/dim]      Get-Content -Wait \"{RALPH_LOG_PATH}\"",
        border_style="blue",
    ))
    console.print("[dim]Streaming node-by-node output below...[/dim]\n")

    graph = build_graph()
    state = initial_state(args.task, repo_dir)
    export_state(state)

    # stream() yields one dict per node as it completes — full visibility
    for step in graph.stream(state, stream_mode="updates"):
        for node_name, node_output in step.items():
            console.print(f"[bold cyan]>> {node_name}[/bold cyan]", end="  ")
            if "plan" in node_output and node_output["plan"]:
                console.print(f"plan ready ({len(node_output['plan'])} chars)")
            elif "code" in node_output and node_output["code"]:
                lines = node_output["code"].count("\n")
                console.print(f"code written ({lines} lines)")
            elif "score" in node_output:
                console.print(f"score={node_output['score']:.2f}  done={node_output.get('done', False)}")
            else:
                console.print(str(list(node_output.keys())))
            # print the latest log entry if present
            if node_output.get("log"):
                console.print(f"   [dim]{node_output['log'][-1]}[/dim]")

        final = {**state, **{k: v for d in step.values() for k, v in d.items()}}
        state = {**state, **final}
        export_state({
            **state,
            "status": f"Running {list(step.keys())[0]}..."
        })

    print_summary(state)
    export_state({"status": "Finished."})
    path = save_run(state)
    console.print(f"\n[dim]Run saved -> {path}[/dim]")


if __name__ == "__main__":
    main()

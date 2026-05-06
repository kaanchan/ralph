"""
RALPH — Recursive Agent Loop with Planner/Handler

Usage:
    python main.py "write a Python function that reverses a string and tests it"
    python main.py --history
"""
import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from graph import build_graph
from memory import save_run, load_runs
from state import RalphState

console = Console()


def initial_state(task: str) -> RalphState:
    return RalphState(
        task=task,
        plan="",
        code="",
        test_output="",
        score=0.0,
        iterations=0,
        model_used="",
        escalated=False,
        done=False,
        log=[],
    )


def print_summary(state: RalphState) -> None:
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
    table.add_row("Success", "✓" if state["done"] or state["score"] >= 0.75 else "✗")
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
            r["task"][:50] + ("…" if len(r["task"]) > 50 else ""),
            str(r["iterations"]),
            f"{r['final_score']:.2f}",
            r["model_used"],
            "yes" if r["escalated"] else "no",
        )
    console.print(table)


def main() -> None:
    p = argparse.ArgumentParser(description="RALPH — local-first coding agent loop")
    p.add_argument("task", nargs="?", help="Coding task to execute")
    p.add_argument("--history", action="store_true", help="Show run history")
    args = p.parse_args()

    if args.history:
        print_history()
        return

    if not args.task:
        p.print_help()
        sys.exit(1)

    console.print(Panel(f"[bold]Task:[/bold] {args.task}", border_style="blue"))

    graph = build_graph()
    state = initial_state(args.task)

    with console.status("[bold green]RALPH loop running…[/bold green]"):
        final = graph.invoke(state)

    print_summary(final)
    path = save_run(final)
    console.print(f"\n[dim]Run saved → {path}[/dim]")


if __name__ == "__main__":
    main()

import json
import time
from pathlib import Path
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text

STATE_FILE = Path(__file__).parent.parent / "logs" / "live_state.json"

def create_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main")
    )
    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1)
    )
    layout["left"].split_column(
        Layout(name="plan", ratio=1),
        Layout(name="code", ratio=1)
    )
    return layout

def update_layout(layout: Layout, state: dict):
    header_text = f"Task: {state.get('task', '')} | Iteration: {state.get('iterations', 0)} | Score: {state.get('score', 0):.2f}"
    layout["header"].update(Panel(Text(header_text, style="bold white"), style="blue", title="RALPH Live State"))
    
    plan = state.get('plan', '')
    layout["plan"].update(Panel(plan or "Waiting for plan...", title="Implementation Plan", border_style="cyan"))
    
    code = state.get('code', '')
    lines = code.splitlines()
    code_preview = "\n".join(lines[:30]) + ("\n..." if len(lines) > 30 else "")
    layout["code"].update(Panel(code_preview or "Waiting for code...", title="Code Preview", border_style="green"))
    
    logs = state.get('logs', [])
    status = state.get('status', '')
    log_text = "".join(logs)
    layout["right"].update(Panel(log_text, title=f"Live Logs - {status}", border_style="yellow"))

def main():
    layout = create_layout()
    with Live(layout, refresh_per_second=4, screen=True):
        while True:
            try:
                if STATE_FILE.exists():
                    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                    update_layout(layout, state)
            except (json.JSONDecodeError, OSError):
                pass
            time.sleep(0.5)

if __name__ == "__main__":
    main()

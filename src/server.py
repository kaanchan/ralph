from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import os

app = FastAPI(title="RALPH Bridge API")

# Enable CORS so the React frontend can talk to this Python server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root directory of the RALPH project
ROOT = Path(__file__).parent.parent
TASKS_ROOT = ROOT / "tasks"

@app.get("/tasks")
def list_tasks():
    """List all available Task Pods."""
    if not TASKS_ROOT.exists():
        return []
    return [d.name for d in TASKS_ROOT.iterdir() if d.is_dir()]

@app.get("/tasks/{name}/graph")
def get_graph(name: str):
    """Retrieve the graph.json for a specific Task Pod."""
    graph_path = TASKS_ROOT / name / "graph.json"
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail=f"graph.json not found in {name}")
    try:
        return json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/{name}/run")
def run_task(name: str):
    """Launch the task execution in a background process with a clean slate."""
    import subprocess
    import os
    task_dir = TASKS_ROOT / name
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    
    # 1. Purge old control signals and crash logs
    control_path = task_dir / "control.json"
    crash_log = task_dir / "CRASH.log"
    try:
        control_path.write_text(json.dumps({"command": ""}), encoding="utf-8")
        if crash_log.exists(): crash_log.unlink()
    except:
        pass
            
    # 2. Setup environment and logs
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    log_file = task_dir / "run_console.log"
    cmd = [str(venv_py), "src/main.py", "run", str(task_dir)]
    
    try:
        f = open(log_file, "w")
    except:
        # Fallback to devnull if log file is locked
        import subprocess as sp
        f = sp.DEVNULL

    subprocess.Popen(
        cmd, 
        cwd=str(ROOT), 
        env=env,
        stdout=f, 
        stderr=f,
        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
    )
    # Note: We don't close 'f' here; it's passed to the subprocess
    return {"status": "launched", "log": str(log_file)}

@app.post("/tasks/{name}/control")
def send_control(name: str, control_data: dict):
    """Send a control signal (pause/abort) to the running task."""
    cmd = control_data.get("command")
    control_path = TASKS_ROOT / name / "control.json"
    control_path.write_text(json.dumps({"command": cmd}), encoding="utf-8")
    return {"status": "signal_sent", "command": cmd}

@app.get("/tasks/{name}/status")
def get_status(name: str):
    """Retrieve the latest execution status by scanning the traces directory."""
    traces_dir = TASKS_ROOT / name / "traces"
    if not traces_dir.exists():
        return {"nodes": {}}
    
    # Find the most recent run directory
    try:
        runs = sorted([d for d in traces_dir.iterdir() if d.is_dir() and d.name.startswith("run_")], key=lambda x: x.name, reverse=True)
        if not runs:
            return {"nodes": {}, "status": "stopped"}
        
        latest_run = runs[0]
        
        # 1. Load run metadata
        run_file = latest_run / "run.json"
        run_metadata = {}
        if run_file.exists():
            try:
                run_metadata = json.loads(run_file.read_text(encoding="utf-8"))
            except: pass
            
        status = run_metadata.get("status", "stopped")
        metrics = run_metadata.get("metrics", {})
        escalated = metrics.get("escalated", False)

        nodes_dir = latest_run / "nodes"
        status_map = {}
        if nodes_dir.exists():
            for node_file in nodes_dir.glob("*.json"):
                try:
                    node_data = json.loads(node_file.read_text(encoding="utf-8"))
                    status_map[node_data["name"]] = {
                        "status": node_data.get("status", "pending"),
                        "duration": node_data.get("duration")
                    }
                except:
                    pass
        return {
            "nodes": status_map, 
            "status": status, 
            "escalated": escalated,
            "run_id": latest_run.name
        }
    except Exception as e:
        return {"nodes": {}, "status": "error", "error": str(e)}

@app.get("/tasks/{name}/logs/console")
def get_console_logs(name: str):
    """Retrieve the main execution console log, prepending any crash reports."""
    task_dir = TASKS_ROOT / name
    log_path = task_dir / "run_console.log"
    crash_path = task_dir / "CRASH.log"
    
    content = ""
    if crash_path.exists():
        content += "🚨 FATAL ENGINE CRASH DETECTED:\n"
        content += "================================\n"
        content += crash_path.read_text(encoding="utf-8")
        content += "\n================================\n\n"

    if log_path.exists():
        content += log_path.read_text(encoding="utf-8")
        
    return {"content": content or "No logs available."}

@app.get("/tasks/{name}/logs/{node_id}")
def get_node_logs(name: str, node_id: str):
    """Retrieve execution logs/metrics for a specific node from the latest run."""
    traces_dir = TASKS_ROOT / name / "traces"
    try:
        runs = sorted([d for d in traces_dir.iterdir() if d.is_dir() and d.name.startswith("run_")], key=lambda x: x.name, reverse=True)
        if not runs:
            return {"content": "No execution data found."}
        
        latest_run = runs[0]
        nodes_dir = latest_run / "nodes"
        
        # We need to find the file that contains "name": node_id
        if nodes_dir.exists():
            for node_file in nodes_dir.glob("*.json"):
                node_data = json.loads(node_file.read_text(encoding="utf-8"))
                if node_data.get("name") == node_id:
                    return {"content": json.dumps(node_data, indent=2)}
        
        return {"content": f"No data yet for node: {node_id}"}
    except Exception as e:
        return {"content": f"Error fetching logs: {str(e)}"}

@app.post("/tasks/{name}/graph")
def save_graph(name: str, graph_data: dict):
    """Save updated graph structure from the React Editor."""
    graph_path = TASKS_ROOT / name / "graph.json"
    try:
        graph_path.write_text(json.dumps(graph_data, indent=2), encoding="utf-8")
        return {"status": "success", "message": f"Graph for {name} updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Run on port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)

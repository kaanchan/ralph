import time
import json
import threading
import queue
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from config import LOGS_DIR, MAX_TOOL_PAYLOAD_KB

TRACES_DIR = LOGS_DIR / "traces"
MAX_STORED_RUNS = 10

class TelemetryDaemon(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.q = queue.Queue()
        self.running = True

    def run(self):
        while self.running:
            try:
                task = self.q.get(timeout=1.0)
                if task is None:
                    break
                func, args = task
                try:
                    func(*args)
                except Exception as e:
                    pass # silent degradation
                self.q.task_done()
            except queue.Empty:
                continue

    def stop(self):
        self.running = False
        self.q.put(None)
        self.join(timeout=2.0)

class TraceManager:
    def __init__(self):
        self.run_id = f"run_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.run_dir = TRACES_DIR / self.run_id
        self.nodes_dir = self.run_dir / "nodes"
        self.tools_dir = self.run_dir / "tools"
        
        self.daemon = TelemetryDaemon()
        
        self.run_state = {
            "id": self.run_id,
            "task": "",
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "status": "running",
            "node_ids": [],
            "metrics": {"total_cost": 0.0, "total_tokens": 0}
        }
        self.active_nodes = {}
        self.active_tools = {}
        
        self._init_fs()
        self.daemon.start()

    def _init_fs(self):
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self.nodes_dir.mkdir(exist_ok=True)
            self.tools_dir.mkdir(exist_ok=True)
            self._prune_old_runs()
        except OSError:
            pass

    def _prune_old_runs(self):
        try:
            runs = sorted([d for d in TRACES_DIR.iterdir() if d.is_dir() and d.name.startswith("run_")], key=lambda x: x.name)
            while len(runs) > MAX_STORED_RUNS:
                old = runs.pop(0)
                shutil.rmtree(old, ignore_errors=True)
        except OSError:
            pass

    def _enqueue(self, func, *args):
        try:
            self.daemon.q.put((func, args), block=False)
        except Exception:
            pass

    def _write_json(self, path: Path, data: dict):
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _truncate(self, payload: str) -> str:
        if not payload:
            return ""
        max_chars = MAX_TOOL_PAYLOAD_KB * 1024
        if len(payload) > max_chars:
            return payload[:max_chars] + f"\n\n...[TRUNCATED: Exceeded {MAX_TOOL_PAYLOAD_KB}KB telemetry limit]"
        return payload

    def set_task(self, task: str):
        self.run_state["task"] = task
        self._sync_run()

    def _sync_run(self):
        self._enqueue(self._write_json, self.run_dir / "run.json", self.run_state.copy())

    def start_node(self, name: str) -> str:
        span_id = f"node_{time.time()}_{name}"
        node = {
            "id": span_id,
            "name": name,
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "status": "running",
            "tool_ids": [],
            "metrics": {}
        }
        self.run_state["node_ids"].append(span_id)
        self.active_nodes[name] = node
        
        self._sync_run()
        self._enqueue(self._write_json, self.nodes_dir / f"{span_id}.json", node.copy())
        return name

    def end_node(self, name: str, status: str = "success", metrics: dict = None):
        if name in self.active_nodes:
            node = self.active_nodes[name]
            node["end_time"] = time.time()
            node["duration"] = node["end_time"] - node["start_time"]
            node["status"] = status
            if metrics:
                node["metrics"] = metrics
            self._enqueue(self._write_json, self.nodes_dir / f"{node['id']}.json", node.copy())

    def start_tool(self, node_name: str, tool_name: str, inputs: str, flags: dict = None) -> str:
        span_id = f"tool_{uuid.uuid4().hex[:8]}"
        tool = {
            "id": span_id,
            "parent_node": node_name,
            "name": tool_name,
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "status": "running",
            "flags": flags or {},
            "inputs": self._truncate(inputs),
            "outputs": None,
            "metrics": {}
        }
        self.active_tools[span_id] = tool
        
        if node_name in self.active_nodes:
            node = self.active_nodes[node_name]
            node["tool_ids"].append(span_id)
            self._enqueue(self._write_json, self.nodes_dir / f"{node['id']}.json", node.copy())
            
        self._enqueue(self._write_json, self.tools_dir / f"{span_id}.json", tool.copy())
        return span_id

    def end_tool(self, span_id: str, status: str, outputs: str, metrics: dict = None):
        if span_id in self.active_tools:
            tool = self.active_tools.pop(span_id)
            tool["end_time"] = time.time()
            tool["duration"] = tool["end_time"] - tool["start_time"]
            tool["status"] = status
            tool["outputs"] = self._truncate(outputs)
            if metrics:
                tool["metrics"] = metrics
            self._enqueue(self._write_json, self.tools_dir / f"{span_id}.json", tool)

    def end_run(self, status: str = "success"):
        self.run_state["end_time"] = time.time()
        if self.run_state["start_time"]:
            self.run_state["duration"] = self.run_state["end_time"] - self.run_state["start_time"]
        self.run_state["status"] = status
        self._sync_run()
        # Do not kill daemon immediately so it finishes writing
        threading.Timer(1.0, self.daemon.stop).start()

tracer = TraceManager()

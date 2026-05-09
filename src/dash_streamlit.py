import json
import time
import streamlit as st
from pathlib import Path
from config import LOGS_DIR, ROOT

st.set_page_config(page_title="RALPH Explorer (Zoomable)", layout="wide")

try:
    from streamlit_agraph import agraph, Node, Edge, Config
except ImportError:
    agraph = None

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except:
        return {}

# --- CSS for Text Wrapping ---
st.markdown("""
    <style>
    /* Force wrap in st.code blocks */
    code {
        white-space: pre-wrap !important;
        word-break: break-all !important;
    }
    .stCode {
        white-space: pre-wrap !important;
    }
    /* Sidebar styling */
    .stButton>button {
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

def format_duration(seconds):
    if seconds is None:
        return "..."
    return f"{seconds:.2f}s"

st.sidebar.title("🤖 RALPH Panel")
st.sidebar.caption("Research & Agentic Logic Planning Hub")

# --- Mode Switcher ---
st.sidebar.markdown("""
    <div style="background: #333; padding: 10px; border-radius: 8px; border: 1px solid #444; margin-bottom: 20px;">
        <p style="margin: 0; font-size: 12px; color: #888;">Switch Mode:</p>
        <div style="display: flex; gap: 10px; margin-top: 5px;">
            <a href="http://localhost:8501" target="_self" style="text-decoration: none; color: #3498db; font-weight: bold; font-size: 14px;">📊 View</a>
            <span style="color: #444;">|</span>
            <a href="http://localhost:3000" target="_blank" style="text-decoration: none; color: #2ecc71; font-weight: bold; font-size: 14px;">🎨 Studio</a>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- Task Pod Discovery (hybrid: filesystem scan + registry + manual) ---
TASKS_ROOT = ROOT / "tasks"

# 1. Auto-discover from tasks/ directory
discovered = {}
if TASKS_ROOT.exists():
    for d in sorted(TASKS_ROOT.iterdir()):
        if d.is_dir():
            discovered[d.name] = str(d)

# 2. Merge with registry (adds tasks from other locations)
registry_file = ROOT / ".ralph_registry.json"
if registry_file.exists():
    registry = read_json(registry_file)
    if isinstance(registry, list):
        for r in registry:
            name = r.get("name", "")
            if name and name not in discovered:
                discovered[name] = r.get("task_dir", "")

# 3. Manual path input
manual_path = st.sidebar.text_input("Or enter a task directory path:")
if manual_path and Path(manual_path).exists():
    discovered[Path(manual_path).name + " (manual)"] = manual_path

task_options = list(discovered.keys()) + ["Global Logs (Legacy)"]
selected_name = st.sidebar.selectbox("Select Task Pod", task_options)

if selected_name == "Global Logs (Legacy)":
    TRACES_DIR = LOGS_DIR / "traces"
else:
    task_dir = discovered.get(selected_name)
    TRACES_DIR = Path(task_dir) / "traces" if task_dir else None

# --- Control Panel (Sidebar) ---
if selected_name != "Global Logs (Legacy)" and task_dir:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🕹️ Control Panel")
    
    # 1. Get current status from latest run
    latest_run_dir = None
    if TRACES_DIR and TRACES_DIR.exists():
        runs = sorted([d for d in TRACES_DIR.iterdir() if d.is_dir() and d.name.startswith("run_")], key=lambda x: x.name, reverse=True)
        if runs: latest_run_dir = runs[0]
        
    status = "stopped"
    if latest_run_dir:
        try:
            r_data = json.loads((latest_run_dir / "run.json").read_text(encoding="utf-8"))
            status = r_data.get("status", "stopped")
        except:
            pass

    col1, col2 = st.sidebar.columns(2)
    
    # Check for pending signals
    control_file = Path(task_dir, "control.json")
    if control_file.exists():
        try:
            pending = json.loads(control_file.read_text())
            cmd = pending.get("command", "").strip()
            if cmd:
                st.sidebar.warning(f"⏳ Pending: {cmd.upper()}")
        except:
            pass

    if status == "running":
        if col1.button("⏸️ Pause", use_container_width=True):
            Path(task_dir, "control.json").write_text(json.dumps({"command": "pause"}))
            st.toast("Pause signal sent!")
            
        if col2.button("⏹️ Abort", use_container_width=True):
            Path(task_dir, "control.json").write_text(json.dumps({"command": "abort"}))
            st.toast("Abort signal sent!")
    else:
        if st.sidebar.button("▶️ Play / Resume", use_container_width=True, type="primary"):
            import subprocess
            import os
            venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
            cmd = [str(venv_py), "src/main.py", "run", str(task_dir)]
            st.sidebar.code(f"Running: {' '.join(cmd)}")
            
            # Ensure environment variables (API keys) are passed
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT)
            
            log_file = Path(task_dir) / "run_console.log"
            # Open log file for the subprocess
            try:
                f = open(log_file, "w")
            except:
                import subprocess as sp
                f = sp.DEVNULL

            # Launch with terminal output restored for debugging
            subprocess.Popen(cmd, cwd=str(ROOT), env=env, creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0)
            st.sidebar.info("🚀 Launching engine...")
            time.sleep(2)
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🚨 Emergency Reset", use_container_width=True, help="Clear stuck signals and reset status"):
        # 1. Clear control.json
        c_file = Path(task_dir, "control.json")
        if c_file.exists(): c_file.unlink()
        
        # 2. Mark latest run as stopped
        if latest_run_dir:
            run_file = latest_run_dir / "run.json"
            if run_file.exists():
                try:
                    r_data = json.loads(run_file.read_text())
                    r_data["status"] = "stopped"
                    run_file.write_text(json.dumps(r_data))
                except: pass
        
        st.toast("System Reset Complete!")
        time.sleep(1)
        st.rerun()


def get_latest_run_dir():
    if not TRACES_DIR or not TRACES_DIR.exists():
        return None
    runs = sorted([d for d in TRACES_DIR.iterdir() if d.is_dir() and d.name.startswith("run_")], key=lambda x: x.name, reverse=True)
    return runs[0] if runs else None

st.title("🤖 RALPH Explorer")
st.caption("Research & Agentic Logic Planning Hub")

run_dir = get_latest_run_dir()
if not run_dir:
    st.info("Waiting for traces... Run a task to register telemetry.")
    time.sleep(1)
    st.rerun()

# Load Run
run_data = read_json(run_dir / "run.json")

tab_log, tab_graph = st.tabs(["📝 Execution Log", "🕸️ Live Topology"])

with tab_log:
    st.header(f"Task: {run_data.get('task', 'N/A')}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Status", run_data.get("status", "Unknown"))
    c2.metric("Total Duration", format_duration(run_data.get("duration")))
    c3.metric("Nodes Executed", len(run_data.get("node_ids", [])))

    metrics = run_data.get("metrics", {})

    # Loop bounds display
    it = metrics.get("iteration", 0)
    esc = metrics.get("escalated", False)
    if esc:
        st.error(f"🚨 **Iteration {it}** - Escalated to Cloud Model")
    elif run_data.get("status") == "running":
        st.info(f"🔄 **Iteration {it} / 5** (Local Boundary)")

    if metrics.get("total_cost") or metrics.get("total_tokens"):
        st.caption(f"Tokens: {metrics.get('total_tokens', 0)} | Cost: ${metrics.get('total_cost', 0):.4f}")

    st.markdown("---")
    st.subheader("Execution Trace")

    nodes_dir = run_dir / "nodes"
    tools_dir = run_dir / "tools"

    for node_id in run_data.get("node_ids", []):
        node = read_json(nodes_dir / f"{node_id}.json")
        if not node: continue
        
        node_name = node.get("name", "Unknown Node")
        node_dur = format_duration(node.get("duration"))
        node_status = node.get("status", "running")
        
        icon = "⏳" if node_status == "running" else ("✅" if node_status == "success" else "❌")
        
        with st.expander(f"{icon} **{node_name.upper()}** - {node_dur}", expanded=True):
            nm = node.get("metrics", {})
            if nm:
                st.json(nm)
                
            tool_ids = node.get("tool_ids", [])
            if not tool_ids:
                st.write("No external tools called.")
                
            for tool_id in tool_ids:
                tool = read_json(tools_dir / f"{tool_id}.json")
                if not tool: continue
                
                t_name = tool.get("name", "tool")
                t_dur = format_duration(tool.get("duration"))
                t_status = tool.get("status", "running")
                t_icon = "🔄" if t_status == "running" else ("✅" if t_status == "success" else "❌")
                
                with st.expander(f"{t_icon} `{t_name}` - {t_dur}"):
                    flags = tool.get("flags", {})
                    t_metrics = tool.get("metrics", {})
                    if flags or t_metrics:
                        fc1, fc2 = st.columns(2)
                        with fc1:
                            if flags: st.caption(f"**Flags/Kwargs:** {flags}")
                        with fc2:
                            if t_metrics: st.caption(f"**Usage/Metrics:** {t_metrics}")
                            
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        st.markdown("**Input / Prompt:**")
                        st.code(tool.get("inputs", ""), language="text")
                    with tc2:
                        st.markdown("**Output / Response:**")
                        out = tool.get("outputs")
                        if out is None:
                            st.info("Running...")
                        else:
                            st.code(out, language="python" if "ollama" in t_name or "aider" in t_name else "text")


with tab_graph:
    if not agraph:
        st.warning("`streamlit-agraph` not installed yet. Please wait or run `pip install streamlit-agraph`.")
    else:
        st.subheader("Interactive Topology View")
        st.caption("Execution Path: Nodes turn Green on success, Red on failure.")
        
        nodes = []
        edges = []
        
        # Build from execution history
        prev_id = None
        for i, node_id in enumerate(run_data.get("node_ids", [])):
            node = read_json(nodes_dir / f"{node_id}.json")
            if not node: continue
            
            n_name = node.get("name", f"Node {i}")
            n_status = node.get("status", "running")
            # Green, Red, Yellow
            color = "#28A745" if n_status == "success" else ("#DC3545" if n_status == "failed" else "#FFC107")
            
            nodes.append(Node(id=node_id, label=n_name.upper(), size=400, color=color, shape="ellipse"))
            if prev_id:
                edges.append(Edge(source=prev_id, target=node_id))
            prev_id = node_id
            
        if not nodes:
            st.info("No nodes executed yet.")
        else:
            config = Config(width=1000, height=500, directed=True, physics=True, hierarchical=False)
            agraph(nodes=nodes, edges=edges, config=config)


if run_data.get("status") == "running":
    time.sleep(1)
    st.rerun()

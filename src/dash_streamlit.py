import json
import time
import streamlit as st
from pathlib import Path
from config import LOGS_DIR

st.set_page_config(page_title="RALPH Explorer (Zoomable)", layout="wide")

TRACES_DIR = LOGS_DIR / "traces"

def get_latest_run_dir():
    if not TRACES_DIR.exists():
        return None
    runs = sorted([d for d in TRACES_DIR.iterdir() if d.is_dir() and d.name.startswith("run_")], key=lambda x: x.name, reverse=True)
    return runs[0] if runs else None

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return {}

def format_duration(seconds):
    if seconds is None:
        return "..."
    return f"{seconds:.2f}s"

st.title("RALPH Telemetry Explorer")
st.caption("Zoomable Distributed Architecture")

run_dir = get_latest_run_dir()
if not run_dir:
    st.info("Waiting for traces... Run `python src/main.py <task>`")
    time.sleep(1)
    st.rerun()

# Load Run
run_data = read_json(run_dir / "run.json")

st.header(f"Task: {run_data.get('task', 'N/A')}")
c1, c2, c3 = st.columns(3)
c1.metric("Status", run_data.get("status", "Unknown"))
c2.metric("Total Duration", format_duration(run_data.get("duration")))
c3.metric("Nodes Executed", len(run_data.get("node_ids", [])))

metrics = run_data.get("metrics", {})
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

if run_data.get("status") == "running":
    time.sleep(1)
    st.rerun()

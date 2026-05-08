import json
import time
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="RALPH Dashboard", layout="wide", initial_sidebar_state="collapsed")

STATE_FILE = Path(__file__).parent.parent / "logs" / "live_state.json"

@st.cache_data(ttl=0.5)
def load_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return None

state = load_state()

if state is None:
    st.warning("Waiting for RALPH live state...")
else:
    st.title(f"RALPH: {state.get('task', 'Idle')}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Iteration", state.get("iterations", 0))
    col2.metric("Score", f"{state.get('score', 0):.2f}")
    col3.metric("Status", state.get("status", "Offline"))
    
    st.markdown("---")
    
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.subheader("Implementation Plan")
        plan = state.get("plan", "")
        if plan:
            st.markdown(plan)
        else:
            st.info("Waiting for plan...")
            
        st.subheader("Generated Code")
        code = state.get("code", "")
        if code:
            st.code(code, language="python")
        else:
            st.info("Waiting for code...")
            
    with right_col:
        st.subheader("Live Logs")
        logs = "".join(state.get("logs", []))
        st.code(logs, language="text")

time.sleep(1)
st.rerun()

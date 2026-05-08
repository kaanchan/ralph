# Multi-Modal Offline Observability & TV-Mode Dashboards

I have successfully implemented a decoupled, "headless backend" architecture for RALPH, enabling true parallel observability and completely transparent internal logging! 

## 1. The Headless State Exporter
I created `src/state_exporter.py`. Now, as `src/main.py` executes its LangGraph loops, it constantly broadcasts its internal state (including the plan, the code, the score, and live streaming logs) into a single atomic JSON file at `logs/live_state.json`.

Because RALPH just blindly writes to this JSON file, you can build *any* frontend you want in any language just by reading that file. I have built three to start you off:

## 2. The Three Dashboards
These can be run **at the exact same time** while RALPH is running:

1. **Terminal Dashboard (`rich`)**
   - Run: `python src/dash_rich.py`
   - A full-screen, split-pane console UI that updates seamlessly.
2. **Vanilla HTML "TV-Mode" Dashboard**
   - Run: `python src/dash_html.py`
   - This spins up a tiny zero-dependency web server and opens your browser. It uses a sleek dark-mode vanilla CSS layout and polls the state every 500ms using native Javascript `fetch()`.
3. **Streamlit App**
   - Run: `streamlit run src/dash_streamlit.py`
   - A modern data-app frontend (ensure you run `pip install -r requirements.txt` first to install Streamlit).

## 3. Destroying the Black Box (Internal Tool Logs)
To ensure that "all internal tools logging systems are respected" as requested, I have introduced a new `RALPH_VERBOSE` mode.

In `src/config.py`, setting the `RALPH_VERBOSE` environment variable to `"1"` enables a massive influx of transparent data:
- `litellm.set_verbose` is turned on.
- The raw `pytest` command arrays and full `stdout/stderr` traces are logged.
- The raw `PROMPT` and `RESPONSE` payloads sent directly to the local Ollama daemon are intercepted.

Instead of flooding the beautiful UI dashboard, all of this low-level execution noise is elegantly routed to a brand new dedicated file: `logs/tools_debug.log`. If you ever wonder *exactly* what command Pytest ran or what string Ollama generated before formatting, it's captured there. 

> [!TIP]
> **Try it out!** 
> 1. Open three terminal tabs.
> 2. In Tab 1, run `python src/dash_rich.py`
> 3. In Tab 2, run `python src/dash_html.py`
> 4. In Tab 3, start RALPH: `python src/main.py "write a simple fibonacci function"`
> 
> Watch your terminal and your web browser synchronize perfectly!

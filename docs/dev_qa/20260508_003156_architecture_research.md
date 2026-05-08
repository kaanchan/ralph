---
date: 2026-05-08T00:31:56-05:00
topic: Architecture Research, LangGraph, Aider, Ollama
---

# Q&A: RALPH Architecture & State of the Art

**Q1: What is my system (RALPH) trying to build?**
**A1:** You are building a cost-optimized, local-first recursive coding agent. It uses LangGraph as the orchestrating "brain" to run a stateful `Plan -> Execute -> Evaluate -> Loop`. To save costs, it tries to use a free local 14B model (`qwen25-coder-14b`) via a direct Ollama API call for file writing, bypassing complex diff formats. If the local model fails multiple times, the system gracefully falls back to a highly capable cloud model (Gemini) using Aider for guaranteed, complex file manipulation.

**Q2: How does this align with industry best practices for LangGraph and Aider?**
**A2:** Your architecture perfectly mirrors state-of-the-art enterprise patterns. Best practices dictate that LangGraph should *never* write code itself; it is purely an orchestrator. Specialized tools (like Aider) should act as "Tool Nodes" within the graph. Furthermore, the community explicitly warns against forcing local 14B models to output structured Aider/Git diff formats (they consistently fail). Your decision to split the local execution into raw API calls for whole-file generation is the established workaround. The "conditional edge fallback" to a cloud model on failure is the premier design pattern for hybrid cost-saving agents.

**Q3: What are the limits of prompts for Ollama and why does it crash/hang?**
**A3:** The hanging is caused by **VRAM / KV Cache Exhaustion**. Ollama allocates memory linearly based on the prompt size (Context Window). If you feed it a massive plan, it attempts to reserve gigabytes of VRAM just for the context. When `Model Weights + KV Cache` exceeds your GPU's VRAM (e.g., 24GB on an RTX 3090), Ollama spills to system RAM over the PCIe bus. This bottleneck drops generation speed from ~30 tokens/sec to ~1 token/sec, causing the client socket to timeout (90s) before generating tokens. You must explicitly cap the context window (e.g., `"num_ctx": 4096`) to prevent this.

**Q4: What are the capabilities of Qwen2.5-Coder-14B?**
**A4:** 
- **Context Limit:** Natively supports up to 131,072 tokens, but this requires massive VRAM. Locally on a 3090, you are limited to ~8k-16k tokens depending on quantization.
- **Prompting:** Expects the ChatML format. Alibaba strongly recommends using the exact system prompt: `"You are Qwen, created by Alibaba Cloud. You are a helpful assistant."`
- **Strengths/Weaknesses:** Excellent at whole-file generation. It struggles with multi-file diffs and "attention degradation" if asked to perform too many sub-tasks in a single prompt. Splitting `solution.py` and `test_solution.py` into separate generation steps is optimal.

"""Agent 1 - RESEARCHER  (model: Qwen3 4B)   A2A server on port 9001
MCP services: duckduckgo (web search) + fetch (read a web page)
Start:  python -m uvicorn specialists.researcher:app --port 9001
"""
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent

import config
import telemetry

INSTRUCTION = """/no_think
You are the Researcher agent. Your only job is to find facts on the web.

Do these steps in order:
1. Call `search` with the topic. Always set max_results to 3.
2. Choose the most useful result and call `fetch` with its URL and max_length 3000.
   If `search` returns no results or an error, do NOT give up: call `fetch` with
   https://en.wikipedia.org/wiki/Special:Search?search=TOPIC&go=Go
   (replace TOPIC with the topic, using + between words).
3. Reply with 5 to 8 short bullet points. Each bullet is one fact and ends with its source URL.

Rules:
- Use only what the tools returned. Never invent facts or URLs.
- If every tool fails, say exactly what failed.
- Do not write reports and do not give opinions.
"""

root_agent = LlmAgent(
    name="researcher_agent",
    model=config.make_llm(config.MODEL_RESEARCHER),
    description="Searches the web and reads pages. Use it to collect facts about a topic. Returns bullet-point facts with source URLs.",
    instruction=INSTRUCTION,
    tools=[
        config.mcp_toolset("duckduckgo", ["search"], agent="researcher_agent"),
        config.mcp_toolset("fetch", ["fetch"], agent="researcher_agent"),
    ],
    generate_content_config=config.gen_config(max_tokens=900),
    **telemetry.callbacks("researcher_agent", config.MODEL_RESEARCHER),  # live tracing for the web UI
)

app = to_a2a(root_agent, host=config.HOST, port=config.PORT_RESEARCHER)

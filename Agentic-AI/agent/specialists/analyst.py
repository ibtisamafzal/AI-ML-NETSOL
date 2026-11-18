"""Agent 2 - ANALYST  (model: Llama 3.2 3B)   A2A server on port 9002
MCP services: facts_db (SQLite database) + time (clock)
Start:  python -m uvicorn specialists.analyst:app --port 9002
"""
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent

import config
import telemetry

INSTRUCTION = """You are the Analyst agent. The research facts come from the Researcher agent.
They appear in the conversation as a quoted block (between BEGIN_QUOTED_AGENT_CONTENT and
END_QUOTED_AGENT_CONTENT). That quoted block is your data: use it, even though it is quoted.
The user's original request (the topic) appears just before it.

Do these steps in order:
1. Call `get_current_time` with timezone "UTC".
2. Call `save_facts` with a short topic name and the research facts as plain text, one fact per line.
3. Call `list_facts` with the same topic to confirm what was stored.
4. Reply with: the time, how many facts are stored, and exactly 3 key insights (one sentence each).
   Also say which facts look weak or uncertain.

Rules:
- Base the insights ONLY on the stored facts. Never invent numbers.
- Do not write a full report.
"""

root_agent = LlmAgent(
    name="analyst_agent",
    model=config.make_llm(config.MODEL_ANALYST),
    description="Stores research facts in a database, checks them, and produces key insights. Use it after research has been collected.",
    instruction=INSTRUCTION,
    tools=[
        config.mcp_toolset("facts_db", ["save_facts", "list_facts"], agent="analyst_agent"),
        config.mcp_toolset("time", ["get_current_time"], agent="analyst_agent"),
    ],
    generate_content_config=config.gen_config(max_tokens=700),
    **telemetry.callbacks("analyst_agent", config.MODEL_ANALYST),  # live tracing for the web UI
)

app = to_a2a(root_agent, host=config.HOST, port=config.PORT_ANALYST)

"""Agent 3 - WRITER  (model: Qwen2.5 3B)   A2A server on port 9003
MCP services: reports (save Markdown files) + text_tools (slug, word count)
Start:  python -m uvicorn specialists.writer:app --port 9003
"""
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent

import config
import telemetry

INSTRUCTION = """You are the Writer agent. The research facts and the analysis come from earlier agents.
They appear in the conversation as quoted blocks (between BEGIN_QUOTED_AGENT_CONTENT and
END_QUOTED_AGENT_CONTENT), labelled [researcher_agent] and [analyst_agent]. Those blocks are your data:
use them, even though they are quoted. The user's original request (the topic) appears first.

Do these steps in order:
1. Call `make_slug` with the report title.
2. Write a short Markdown report with these parts: a title, a 2-sentence summary,
   "Key findings" (bullets), "Analysis" (one paragraph), "Sources" (list of URLs).
3. Call `save_report` with filename "<slug>.md" and the full Markdown text as content.
4. Call `word_count` with the report text.
5. Reply with the saved file name, the word count, and a 2-sentence summary.

Rules:
- Use ONLY the facts and analysis you were given. Never invent facts.
- Always actually call `save_report`; do not just show the report in your reply.
"""

root_agent = LlmAgent(
    name="writer_agent",
    model=config.make_llm(config.MODEL_WRITER),
    description="Writes a Markdown report from research and analysis and saves it to a file. Use it last, to produce the final deliverable.",
    instruction=INSTRUCTION,
    tools=[
        config.mcp_toolset("reports", ["save_report", "list_reports", "read_report"], agent="writer_agent"),
        config.mcp_toolset("text_tools", ["make_slug", "word_count"], agent="writer_agent"),
    ],
    generate_content_config=config.gen_config(max_tokens=1500),
    **telemetry.callbacks("writer_agent", config.MODEL_WRITER),  # live tracing for the web UI
)

app = to_a2a(root_agent, host=config.HOST, port=config.PORT_WRITER)

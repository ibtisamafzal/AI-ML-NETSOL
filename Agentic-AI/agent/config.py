"""Central settings: models, ports, and how each MCP server is launched.

Change model names here (or with environment variables) -- nothing else needs editing.
Run `ollama list` to see the exact names of the models you pulled.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- Ollama / models
OLLAMA_BASE = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")

MODEL_RESEARCHER = os.environ.get("MODEL_RESEARCHER", "hf.co/Qwen/Qwen3-4B-GGUF:Q4_K_M")
MODEL_ANALYST = os.environ.get("MODEL_ANALYST", "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M")
MODEL_WRITER = os.environ.get("MODEL_WRITER", "hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M")
MODEL_ROUTER = os.environ.get("MODEL_ROUTER", MODEL_WRITER)  # only used in "router" mode

NUM_CTX = int(os.environ.get("NUM_CTX", "8192"))  # context window (tokens) given to Ollama

# ---------------------------------------------------------------- A2A servers
HOST = "127.0.0.1"
PORT_RESEARCHER = 9001
PORT_ANALYST = 9002
PORT_WRITER = 9003
A2A_TIMEOUT = float(os.environ.get("A2A_TIMEOUT", "900"))  # CPU inference is slow: seconds allowed per call

# ---------------------------------------------------------------- web UI
UI_PORT = int(os.environ.get("UI_PORT", "8765"))

# ---------------------------------------------------------------- MCP servers
TIMEZONE = os.environ.get("TIMEZONE", "UTC")
MCP_TIMEOUT = float(os.environ.get("MCP_TIMEOUT", "60"))  # seconds to start/connect to an MCP server

_MCP_DIR = ROOT / "mcp_servers"

# name -> how to start it. Every server is a local child process talking over stdio.
SERVERS = {
    # third-party servers installed by pip
    "duckduckgo": {
        "args": ["-c", "from duckduckgo_mcp_server.server import main; main()"],
        "env": {"DDG_REF_URL_THRESHOLD": "0"},  # 0 = never shorten URLs (small models get confused by ref:// tokens)
    },
    "fetch": {"args": ["-m", "mcp_server_fetch"]},
    "time": {"args": ["-m", "mcp_server_time", "--local-timezone", TIMEZONE]},
    # our own small servers (see mcp_servers/)
    "facts_db": {"args": [str(_MCP_DIR / "facts_db_server.py")]},
    "reports": {"args": [str(_MCP_DIR / "reports_server.py")]},
    "text_tools": {"args": [str(_MCP_DIR / "text_tools_server.py")]},
}


def make_llm(model_name: str):
    """An ADK model object that talks to a local Ollama model through LiteLLM.

    The prefix must be `ollama_chat/` (not `ollama/`), otherwise tool calling loops.
    """
    from google.adk.models.lite_llm import LiteLlm

    return LiteLlm(model=f"ollama_chat/{model_name}", api_base=OLLAMA_BASE, num_ctx=NUM_CTX)


def gen_config(max_tokens: int = 1024):
    """Low temperature = fewer random mistakes from small models."""
    from google.genai import types

    return types.GenerateContentConfig(temperature=0.2, max_output_tokens=max_tokens)


def mcp_toolset(name: str, tools: list[str] | None = None, agent: str = ""):
    """Connect an agent to one MCP server. `tools` limits which tools the model can see.

    `agent` is only used by the web UI to label trace events.
    """
    import telemetry
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from mcp import StdioServerParameters

    spec = SERVERS[name]
    params = StdioServerParameters(command=sys.executable, args=spec["args"], env=spec.get("env"))
    shown = " ".join(["python"] + [Path(a).name if os.sep in a else a for a in spec["args"]])
    return telemetry.traced_toolset_class()(
        connection_params=StdioConnectionParams(server_params=params, timeout=MCP_TIMEOUT),
        tool_filter=tools,
        server_name=name,
        agent_name=agent,
        command=shown,
    )


# ---------------------------------------------------------------- what the web UI draws
# (purely descriptive: the real wiring is in specialists/*.py)
UI_AGENTS = [
    {"name": "researcher_agent", "label": "Researcher", "port": PORT_RESEARCHER, "model": MODEL_RESEARCHER,
     "servers": [{"name": "duckduckgo", "desc": "Web search"}, {"name": "fetch", "desc": "Read web pages"}]},
    {"name": "analyst_agent", "label": "Analyst", "port": PORT_ANALYST, "model": MODEL_ANALYST,
     "servers": [{"name": "facts_db", "desc": "SQLite facts database"}, {"name": "time", "desc": "Clock"}]},
    {"name": "writer_agent", "label": "Writer", "port": PORT_WRITER, "model": MODEL_WRITER,
     "servers": [{"name": "reports", "desc": "Save Markdown reports"}, {"name": "text_tools", "desc": "Slug and word count"}]},
]

"""Checks your setup before you run the agents:   python check_setup.py

1. Python packages are installed
2. Ollama is running, the three models exist, and they support tool calling
3. Every MCP server starts and lists its tools
"""
import asyncio
import json
import sys
import urllib.request

import config

problems = 0


def report(ok: bool, text: str) -> None:
    global problems
    problems += 0 if ok else 1
    print(f"[{' OK ' if ok else 'FAIL'}] {text}")


def check_packages() -> None:
    print("\n1) Python packages")
    report(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]} (need 3.10 or newer)")
    for module in ["google.adk", "a2a", "litellm", "mcp", "uvicorn", "fastapi", "httpx",
                   "duckduckgo_mcp_server", "mcp_server_fetch", "mcp_server_time"]:
        try:
            __import__(module)
            report(True, module)
        except Exception as exc:
            report(False, f"{module}: {exc}  -> run: pip install -r requirements.txt")


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        config.OLLAMA_BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def check_ollama() -> None:
    print("\n2) Ollama and models")
    try:
        with urllib.request.urlopen(config.OLLAMA_BASE + "/api/tags", timeout=5) as r:
            installed = {m["name"] for m in json.loads(r.read())["models"]}
        report(True, f"Ollama is running at {config.OLLAMA_BASE}")
    except Exception as exc:
        report(False, f"Cannot reach Ollama at {config.OLLAMA_BASE} ({exc}). Start it with: ollama serve")
        return
    wanted = {
        "researcher": config.MODEL_RESEARCHER,
        "analyst": config.MODEL_ANALYST,
        "writer": config.MODEL_WRITER,
    }
    for role, model in wanted.items():
        found = model in installed or f"{model}:latest" in installed
        if not found:
            report(False, f"{role}: model '{model}' not found. Run `ollama list` and fix the name in config.py")
            continue
        try:
            caps = _post("/api/show", {"model": model}).get("capabilities", [])
        except Exception as exc:
            report(False, f"{role}: could not inspect '{model}' ({exc})")
            continue
        if "tools" in caps:
            report(True, f"{role}: {model} (tool calling supported)")
        else:
            report(False, f"{role}: {model} does NOT support tool calling (capabilities: {caps}). "
                          "Pick another model in config.py")


async def _list_tools(name: str) -> list[str]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    spec = config.SERVERS[name]
    params = StdioServerParameters(command=sys.executable, args=spec["args"], env=spec.get("env"))
    async with asyncio.timeout(90):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return [t.name for t in (await session.list_tools()).tools]


def check_mcp() -> None:
    print("\n3) MCP servers (each is started briefly, then stopped)")
    for name in config.SERVERS:
        try:
            tools = asyncio.run(_list_tools(name))
            report(True, f"{name}: {', '.join(tools)}")
        except BaseException as exc:  # noqa: BLE001
            report(False, f"{name}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    check_packages()
    check_ollama()
    if "--skip-mcp" not in sys.argv:
        check_mcp()
    print("\nAll checks passed." if problems == 0 else f"\n{problems} problem(s) found. Fix the FAIL lines above.")
    sys.exit(1 if problems else 0)

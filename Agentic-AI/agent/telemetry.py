"""Live tracing for the agents (feeds the web UI).

What it records, per agent:
  agent.start / agent.end   an agent begins / finishes its task          (+ the message it received)
  mcp.connect               an MCP server was started/connected, tools discovered, how long it took
  llm.start / llm.end       one call to the local model: prompt, answer, tokens, speed, duration
  tool.start / tool.end     one MCP tool call: arguments, result, duration, success
  tool.error                a tool crashed: the error is handled and shown to the model so it can adapt

Events are sent to the UI server in a background thread. If the UI is not running they are simply dropped,
so the agents work exactly the same with or without the UI. Set TELEMETRY=0 to switch everything off.
"""
import json
import os
import queue
import threading
import time
import urllib.request
import uuid
from typing import Any, Callable, Optional

URL = os.environ.get("TELEMETRY_URL", "http://127.0.0.1:8765/api/ingest")
ENABLED = os.environ.get("TELEMETRY", "1") != "0"

TOOL_SERVER: dict[str, str] = {}  # tool name -> MCP server name (filled when tools are discovered)

_sink: Optional[Callable[[dict], None]] = None
_queue: "queue.Queue[dict]" = queue.Queue(maxsize=2000)
_worker: Optional[threading.Thread] = None
_worker_lock = threading.Lock()
_down_until = 0.0
_open: dict[tuple, tuple[str, float]] = {}  # (kind, key) -> (span id, perf_counter start)


# ------------------------------------------------------------------ delivery
def set_sink(fn: Optional[Callable[[dict], None]]) -> None:
    """Deliver events in-process (used by the UI server itself) instead of over HTTP."""
    global _sink
    _sink = fn


def _post_forever() -> None:
    global _down_until
    while True:
        event = _queue.get()
        if time.time() < _down_until:
            continue  # UI is offline: drop quietly instead of piling up
        try:
            req = urllib.request.Request(
                URL, data=json.dumps(event, default=str).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            urllib.request.urlopen(req, timeout=1.5).read()
        except Exception:
            _down_until = time.time() + 5


def emit(type_: str, agent: str, **data: Any) -> None:
    if not ENABLED:
        return
    event = {"type": type_, "agent": agent, "ts": time.time(), **data}
    if _sink is not None:
        try:
            _sink(event)
        except Exception:
            pass
        return
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = threading.Thread(target=_post_forever, name="telemetry", daemon=True)
            _worker.start()
    try:
        _queue.put_nowait(event)
    except queue.Full:
        pass


# ------------------------------------------------------------------ helpers
def clip(value: Any, limit: int = 2000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + f"... [+{len(text) - limit} more characters]"


def _safe(obj: Any, limit: int = 1500) -> Any:
    """JSON-safe copy with long strings clipped."""
    if isinstance(obj, str):
        return clip(obj, limit)
    if isinstance(obj, dict):
        return {str(k): _safe(v, limit) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(v, limit) for v in obj][:30]
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return clip(str(obj), limit)


def _content_text(content: Any) -> str:
    parts = getattr(content, "parts", None) or []
    return "\n".join(p.text for p in parts if getattr(p, "text", None))


def _part_summary(part: Any) -> dict:
    if getattr(part, "function_call", None):
        fc = part.function_call
        return {"kind": "call", "name": fc.name, "args": _safe(dict(fc.args or {}), 800)}
    if getattr(part, "function_response", None):
        fr = part.function_response
        return {"kind": "result", "name": fr.name, "text": clip(_result_text(fr.response), 1200)}
    return {"kind": "text", "text": clip(getattr(part, "text", "") or "", 3000)}


def _result_text(resp: Any) -> str:
    """Flatten an MCP tool response into readable text."""
    if isinstance(resp, dict):
        content = resp.get("content")
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            if texts:
                return "\n".join(texts)
        if "result" in resp and isinstance(resp["result"], str):
            return resp["result"]
    return resp if isinstance(resp, str) else json.dumps(resp, default=str, ensure_ascii=False)


def _is_error(resp: Any) -> bool:
    if isinstance(resp, dict):
        if resp.get("isError") or resp.get("is_error"):
            return True
        if "error" in resp and len(resp) <= 3:
            return True
    return False


_SOFT_FAIL = None


def _soft_failure(text: str) -> bool:
    """True when a tool technically succeeded but returned no usable data (e.g. 'No results were found')."""
    global _SOFT_FAIL
    if _SOFT_FAIL is None:
        import re
        _SOFT_FAIL = re.compile(r"^\s*(no results|no matches|nothing found|error|failed|unable to|could not|cannot)|bot detection",
                                re.IGNORECASE)
    return not text.strip() or bool(_SOFT_FAIL.search(text[:300]))


def _begin(kind: str, key: Any) -> str:
    sid = uuid.uuid4().hex[:8]
    _open[(kind, key)] = (sid, time.perf_counter())
    return sid


def _finish(kind: str, key: Any) -> tuple[Optional[str], float]:
    item = _open.pop((kind, key), None)
    if item is None:
        return None, 0.0
    return item[0], (time.perf_counter() - item[1]) * 1000


# ------------------------------------------------------------------ ADK callbacks
def callbacks(agent_name: str, model_name: str) -> dict:
    """Keyword arguments for LlmAgent(...) that trace everything this agent does.

    ADK calls these hooks by keyword, so the parameter names must not be changed.
    """

    def before_agent(callback_context):
        sid = _begin("agent", callback_context.invocation_id)
        emit("agent.start", agent_name, sid=sid, model=model_name,
             input=clip(_content_text(getattr(callback_context, "user_content", None)), 6000))
        return None

    def after_agent(callback_context):
        sid, ms = _finish("agent", callback_context.invocation_id)
        if sid:
            emit("agent.end", agent_name, sid=sid, ms=round(ms))
        return None

    def before_model(callback_context, llm_request):
        key = callback_context.invocation_id
        sid = _begin("llm", key)
        cfg = getattr(llm_request, "config", None)
        contents = list(getattr(llm_request, "contents", None) or [])
        messages = [
            {"role": c.role or "user", "parts": [_part_summary(p) for p in (c.parts or [])][:8]}
            for c in contents[-12:]
        ]
        system = _content_text(getattr(cfg, "system_instruction", None)) if cfg else ""
        if not system and cfg and isinstance(getattr(cfg, "system_instruction", None), str):
            system = cfg.system_instruction
        chars = len(system) + sum(len(json.dumps(m, default=str)) for m in messages)
        emit("llm.start", agent_name, sid=sid, model=model_name, system=clip(system, 8000),
             messages=messages, tools=list((getattr(llm_request, "tools_dict", None) or {}).keys()),
             temperature=getattr(cfg, "temperature", None), max_tokens=getattr(cfg, "max_output_tokens", None),
             prompt_chars=chars)
        return None

    def after_model(callback_context, llm_response):
        sid, ms = _finish("llm", callback_context.invocation_id)
        if not sid:
            return None
        parts = getattr(getattr(llm_response, "content", None), "parts", None) or []
        text = "\n".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False))
        calls = [{"name": p.function_call.name, "args": _safe(dict(p.function_call.args or {}), 600)}
                 for p in parts if getattr(p, "function_call", None)]
        usage = getattr(llm_response, "usage_metadata", None)
        tok_in = getattr(usage, "prompt_token_count", None)
        tok_out = getattr(usage, "candidates_token_count", None)
        err = getattr(llm_response, "error_message", None)
        emit("llm.end", agent_name, sid=sid, ms=round(ms), text=clip(text, 6000), calls=calls,
             tokens_in=tok_in, tokens_out=tok_out,
             tok_per_s=round(tok_out / (ms / 1000), 1) if tok_out and ms else None,
             ok=not err, error=err)
        return None

    def on_model_error(callback_context, llm_request, error):
        sid, ms = _finish("llm", callback_context.invocation_id)
        emit("llm.error", agent_name, sid=sid, ms=round(ms), error=clip(f"{type(error).__name__}: {error}", 1500),
             handled=False, recovery="Not recoverable here: the stage fails and the pipeline stops.")
        return None  # let ADK raise: a broken model means a failed stage, and the UI shows it

    def before_tool(tool, args, tool_context):
        key = getattr(tool_context, "function_call_id", None) or tool.name
        sid = _begin("tool", key)
        emit("tool.start", agent_name, sid=sid, tool=tool.name, server=TOOL_SERVER.get(tool.name, "local"),
             args=_safe(args))
        return None

    def after_tool(tool, args, tool_context, tool_response):
        key = getattr(tool_context, "function_call_id", None) or tool.name
        sid, ms = _finish("tool", key)
        if not sid:  # already closed by on_tool_error
            return None
        text = _result_text(tool_response)
        failed = _is_error(tool_response)
        soft = (not failed) and _soft_failure(text)
        emit("tool.end", agent_name, sid=sid, tool=tool.name, server=TOOL_SERVER.get(tool.name, "local"),
             ms=round(ms), ok=not failed, warn=soft, result=clip(text, 5000), result_chars=len(text),
             recovery=("The error text was returned to the model, which can retry or use another tool."
                       if failed else
                       "The tool ran but returned no usable data. The model decides what to do next (see its fallback step)."
                       if soft else None))
        return None

    def on_tool_error(tool, args, tool_context, error):
        key = getattr(tool_context, "function_call_id", None) or tool.name
        sid, ms = _finish("tool", key)
        message = f"{type(error).__name__}: {error}"
        emit("tool.error", agent_name, sid=sid, tool=tool.name, server=TOOL_SERVER.get(tool.name, "local"),
             ms=round(ms), error=clip(message, 1500), handled=True,
             recovery="Caught. The error was returned to the model as the tool result so it can adapt.")
        return {"error": message, "hint": "This tool failed. Try different arguments or another tool, or say that it failed."}

    return {
        "before_agent_callback": before_agent,
        "after_agent_callback": after_agent,
        "before_model_callback": before_model,
        "after_model_callback": after_model,
        "on_model_error_callback": on_model_error,
        "before_tool_callback": before_tool,
        "after_tool_callback": after_tool,
        "on_tool_error_callback": on_tool_error,
    }


# ------------------------------------------------------------------ traced MCP toolset
_TRACED_CLASS = None


def traced_toolset_class():
    """McpToolset subclass that reports when an MCP server is started and which tools it offers."""
    global _TRACED_CLASS
    if _TRACED_CLASS is not None:
        return _TRACED_CLASS
    from google.adk.tools.mcp_tool import McpToolset

    class TracedMcpToolset(McpToolset):
        def __init__(self, *args, server_name: str = "", agent_name: str = "", command: str = "", **kwargs):
            super().__init__(*args, **kwargs)
            self._t_server = server_name
            self._t_agent = agent_name
            self._t_command = command
            self._t_last_invocation = None
            self._t_cold = True

        async def get_tools(self, readonly_context=None):
            invocation = getattr(readonly_context, "invocation_id", None)
            started = time.perf_counter()
            try:
                tools = await super().get_tools(readonly_context)
            except Exception as exc:
                emit("mcp.error", self._t_agent, server=self._t_server,
                     ms=round((time.perf_counter() - started) * 1000),
                     error=clip(f"{type(exc).__name__}: {exc}", 1500), handled=False,
                     recovery="MCP server could not be reached: the stage fails.")
                raise
            for t in tools:
                TOOL_SERVER[t.name] = self._t_server
            if invocation != self._t_last_invocation:  # report once per task, not once per model call
                self._t_last_invocation = invocation
                emit("mcp.connect", self._t_agent, server=self._t_server, command=self._t_command,
                     tools=[t.name for t in tools], ms=round((time.perf_counter() - started) * 1000),
                     cold=self._t_cold)
            self._t_cold = False
            return tools

    _TRACED_CLASS = TracedMcpToolset
    return _TRACED_CLASS

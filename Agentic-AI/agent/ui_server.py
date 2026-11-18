"""Web UI server: runs the orchestrator and streams a live trace of everything to the browser.

    python ui_server.py            (or just `python run_all.py`, which starts it for you)
    open http://127.0.0.1:8765

Where the trace data comes from:
  * this process  : the orchestrator, the A2A requests/responses (via an instrumented HTTP client)
  * the agents    : LLM calls, MCP tool calls, MCP start-up, errors (via telemetry.py -> POST /api/ingest)
"""
import asyncio
import json
import re
import sys
import time
import traceback
import uuid
import warnings
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore")

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

import config  # noqa: E402
import telemetry  # noqa: E402
from orchestrator import StageFailedError, build_orchestrator  # noqa: E402

INDEX_HTML = config.ROOT / "ui" / "index.html"
RUNS_DIR = config.ROOT / "runs"
REPORTS_DIR = config.ROOT / "reports"
PORT_TO_AGENT = {a["port"]: a["name"] for a in config.UI_AGENTS}


# ====================================================================== run + hub
class Run:
    def __init__(self, prompt: str, mode: str):
        self.id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        self.prompt, self.mode = prompt, mode
        self.started = time.time()
        self.events: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()
        self.done = False
        self.status = "running"
        self.ms = 0
        self.task: Optional[asyncio.Task] = None
        self.hops: dict[str, str] = {}  # agent -> span id of its open A2A hop

    def add(self, type_: str, agent: str = "orchestrator", **data) -> dict:
        event = {"i": len(self.events), "t": round((time.time() - self.started) * 1000), "type": type_,
                 "agent": agent, **data}
        self.events.append(event)
        for q in list(self.subscribers):
            q.put_nowait(event)
        return event

    def summary(self) -> dict:
        return {"id": self.id, "prompt": self.prompt, "mode": self.mode, "started": self.started,
                "status": self.status, "ms": self.ms}

    def save(self) -> None:
        RUNS_DIR.mkdir(exist_ok=True)
        (RUNS_DIR / f"{self.id}.json").write_text(
            json.dumps({**self.summary(), "events": self.events}, ensure_ascii=False), encoding="utf-8")


class Hub:
    def __init__(self):
        self.runs: dict[str, Run] = {}
        self.active: Optional[Run] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.warming = False
        self.seen: dict[str, tuple[float, dict]] = {}  # agent -> (time last answered, its card)

    def ingest(self, event: dict) -> bool:
        """Attach an event reported by an agent to the active run (thread-safe)."""
        def _add():
            run = self.active
            if run is None or run.done:
                return
            data = {k: v for k, v in event.items() if k not in ("type", "agent")}
            run.add(event.get("type", "event"), event.get("agent", "unknown"), **data)

        if self.loop is not None:
            self.loop.call_soon_threadsafe(_add)
        return True

    def history(self) -> list[dict]:
        items = {r.id: r.summary() for r in self.runs.values()}
        if RUNS_DIR.exists():
            for f in RUNS_DIR.glob("*.json"):
                if f.stem not in items:
                    try:
                        d = json.loads(f.read_text(encoding="utf-8"))
                        items[f.stem] = {k: d.get(k) for k in ("id", "prompt", "mode", "started", "status", "ms")}
                    except Exception:
                        pass
        return sorted(items.values(), key=lambda r: r.get("started") or 0, reverse=True)[:50]


hub = Hub()
app = FastAPI(title="Agent pipeline UI")


# ====================================================================== orchestrator run
async def preflight(run: Run) -> bool:
    """Fail fast with a clear message if Ollama or an agent is not running."""
    async with httpx.AsyncClient(timeout=8) as client:
        started = time.perf_counter()
        try:
            await client.get(config.OLLAMA_BASE + "/api/tags")
            run.add("preflight", "orchestrator", target="ollama", ok=True,
                    ms=round((time.perf_counter() - started) * 1000))
        except Exception as exc:
            run.add("error", "orchestrator", where="preflight", message=f"Ollama is not reachable at {config.OLLAMA_BASE}",
                    detail=str(exc), handled=True, recovery="Run stopped before starting. Start it with: ollama serve")
            return False
        for agent in config.UI_AGENTS:
            started = time.perf_counter()
            try:
                r = await client.get(f"http://{config.HOST}:{agent['port']}/.well-known/agent-card.json")
                r.raise_for_status()
                run.add("preflight", agent["name"], target="agent-card", ok=True, port=agent["port"],
                        ms=round((time.perf_counter() - started) * 1000))
            except Exception as exc:
                run.add("error", agent["name"], where="preflight",
                        message=f"{agent['label']} agent is offline (port {agent['port']})", detail=str(exc),
                        handled=True, recovery="Run stopped before starting. Start the agents with: python run_all.py")
                return False
    return True


def _trace_client(run: Run) -> httpx.AsyncClient:
    """HTTP client for the orchestrator that records every A2A call."""

    def agent_of(url: httpx.URL) -> str:
        return PORT_TO_AGENT.get(url.port or 0, str(url.host))

    async def on_request(request: httpx.Request):
        request.extensions["trace_t0"] = time.perf_counter()
        agent = agent_of(request.url)
        if request.url.path.endswith("agent-card.json"):
            return
        body = ""
        try:
            body = request.content.decode("utf-8")
            payload = json.loads(body)
        except Exception:
            payload = body[:2000]
        sid = "hop-" + uuid.uuid4().hex[:6]
        run.hops[agent] = sid
        run.add("a2a.request", agent, sid=sid, url=str(request.url), method="POST", bytes=len(body),
                payload=telemetry._safe(payload, 4000))

    async def on_response(response: httpx.Response):
        t0 = response.request.extensions.get("trace_t0", time.perf_counter())
        ms = round((time.perf_counter() - t0) * 1000)
        agent = agent_of(response.request.url)
        if response.request.url.path.endswith("agent-card.json"):
            card = None
            try:
                await response.aread()
                card = response.json()
            except Exception:
                pass
            run.add("a2a.discover", agent, url=str(response.request.url), status=response.status_code, ms=ms,
                    card=telemetry._safe(card, 600) if card else None)
        else:
            run.add("a2a.accepted", agent, sid=run.hops.get(agent), status=response.status_code, ms=ms,
                    content_type=response.headers.get("content-type", ""))

    return httpx.AsyncClient(timeout=config.A2A_TIMEOUT,
                             event_hooks={"request": [on_request], "response": [on_response]})


async def execute(run: Run) -> None:
    session_service = InMemorySessionService()
    client: Optional[httpx.AsyncClient] = None
    texts: dict[str, str] = {}
    counts: dict[str, int] = {}
    started: dict[str, float] = {}
    current: Optional[str] = None
    final_author = None
    last_state: dict[str, str] = {}

    def close_hop(agent: Optional[str]):
        if agent and agent in started:
            run.add("a2a.response", agent, sid=run.hops.get(agent), events=counts.get(agent, 0),
                    ms=round((time.perf_counter() - started.pop(agent)) * 1000), text=telemetry.clip(texts.get(agent, ""), 6000))

    try:
        run.add("run.start", "orchestrator", prompt=run.prompt, mode=run.mode)
        if not await preflight(run):
            return await finish(run, "failed", error="Pre-flight check failed")
        client = _trace_client(run)
        runner = Runner(app_name="ui", agent=build_orchestrator(run.mode, httpx_client=client),
                        session_service=session_service, auto_create_session=True)
        message = types.Content(role="user", parts=[types.Part(text=run.prompt)])
        async for event in runner.run_async(user_id="ui", session_id=run.id, new_message=message):
            author = event.author
            if author and author not in ("user",) and author in PORT_TO_AGENT.values():
                if author != current:
                    close_hop(current)
                    current = author
                    started[author] = time.perf_counter()
                counts[author] = counts.get(author, 0) + 1
                state = str((((event.custom_metadata or {}).get("a2a:response") or {}).get("status") or {}).get("state", ""))
                if state and last_state.get(author) != state:  # A2A task lifecycle: submitted -> working -> completed
                    last_state[author] = state
                    run.add("a2a.state", author, sid=run.hops.get(author), state=state.replace("TASK_STATE_", "").lower())
            for part in (event.content.parts if event.content else []) or []:
                if getattr(part, "function_call", None) and part.function_call.name == "transfer_to_agent":
                    run.add("route", author, target=(part.function_call.args or {}).get("agent_name"))
                if getattr(part, "text", None) and not getattr(part, "thought", False) and event.is_final_response():
                    texts[author] = part.text.strip()
                    final_author = author
        close_hop(current)
        await finish(run, "ok", result=texts.get(final_author or "", ""), result_agent=final_author)
    except asyncio.CancelledError:
        await finish(run, "cancelled")
    except Exception as exc:  # noqa: BLE001
        close_hop(current)
        stage = exc.agent if isinstance(exc, StageFailedError) else (current or "orchestrator")
        tb = [line for line in traceback.format_exc().strip().splitlines() if line.strip()][-6:]
        kind = type(exc).__name__
        if isinstance(exc, StageFailedError):
            message = exc.detail[:600]
            hint = "Pipeline stopped at this stage. Later agents were NOT run, so they cannot work from bad input."
        elif isinstance(exc, (httpx.HTTPError, ConnectionError)):
            message, hint = f"{kind}: {str(exc)[:500]}", "The agent stopped answering. Check logs/*.log and that Ollama is running."
        else:
            message, hint = f"{kind}: {str(exc)[:600]}", "Unexpected error. The run was stopped."
        run.add("error", stage, where="stage" if isinstance(exc, StageFailedError) else "pipeline", message=message,
                detail="\n".join(tb), handled=False, recovery=hint)
        await finish(run, "failed", error=f"{kind}: {str(exc)[:200]}")
    finally:
        if client is not None:
            await client.aclose()


async def finish(run: Run, status: str, **extra) -> None:
    run.status = status
    run.ms = round((time.time() - run.started) * 1000)
    report = None
    for ev in run.events:
        if ev["type"] == "tool.end" and ev.get("tool") == "save_report" and ev.get("ok"):
            m = re.search(r"report to (.+?) \(", ev.get("result", ""))
            if m:
                report = Path(m.group(1)).name
    run.add("run.end", "orchestrator", status=status, ms=run.ms, report=report, **extra)
    run.done = True
    run.save()


# ====================================================================== API
@app.on_event("startup")
async def _startup():
    hub.loop = asyncio.get_running_loop()
    telemetry.set_sink(hub.ingest)  # the router agent runs inside this process


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.post("/api/ingest")
async def ingest(request: Request):
    return {"ok": hub.ingest(await request.json())}


@app.get("/api/status")
async def status():
    out = {"ollama": {"up": False, "loaded": [], "warming": hub.warming}, "agents": [], "mode_default": "pipeline"}
    async with httpx.AsyncClient(timeout=5) as client:  # generous: the CPU is busy while models run
        loaded: list[str] = []
        try:
            await client.get(config.OLLAMA_BASE + "/api/tags")
            out["ollama"]["up"] = True
            ps = await client.get(config.OLLAMA_BASE + "/api/ps")
            loaded = [m.get("name", "") for m in ps.json().get("models", [])]
            out["ollama"]["loaded"] = loaded
        except Exception:
            pass
        for agent in config.UI_AGENTS:
            info = {**agent, "online": False, "card": None,
                    "loaded": any(agent["model"] == n or n.startswith(agent["model"]) for n in loaded)}
            try:
                r = await client.get(f"http://{config.HOST}:{agent['port']}/.well-known/agent-card.json")
                info["online"], info["card"] = r.status_code == 200, r.json()
                if info["online"]:
                    hub.seen[agent["name"]] = (time.time(), info["card"])
            except Exception:
                prev = hub.seen.get(agent["name"])
                if prev and time.time() - prev[0] < 30:  # one slow answer is not "offline"
                    info["online"], info["card"], info["stale"] = True, prev[1], True
            out["agents"].append(info)
    return out


@app.post("/api/warmup")
async def warmup():
    if hub.warming:
        return {"ok": True, "already": True}

    async def _warm():
        hub.warming = True
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                for model in dict.fromkeys(a["model"] for a in config.UI_AGENTS):
                    try:
                        await client.post(config.OLLAMA_BASE + "/api/generate",
                                          json={"model": model, "prompt": "", "keep_alive": "30m", "stream": False})
                    except Exception:
                        pass
        finally:
            hub.warming = False

    asyncio.create_task(_warm())
    return {"ok": True}


@app.post("/api/runs")
async def start_run(request: Request):
    body = await request.json()
    prompt = (body.get("prompt") or "").strip()
    mode = body.get("mode") if body.get("mode") in ("pipeline", "router") else "pipeline"
    if not prompt:
        raise HTTPException(400, "Empty prompt")
    if hub.active and not hub.active.done:
        raise HTTPException(409, "A run is already in progress")
    run = Run(prompt[:2000], mode)
    hub.runs[run.id] = run
    hub.active = run
    run.task = asyncio.create_task(execute(run))
    return {"id": run.id}


@app.post("/api/runs/{run_id}/cancel")
async def cancel(run_id: str):
    run = hub.runs.get(run_id)
    if run and run.task and not run.done:
        run.task.cancel()
    return {"ok": True}


@app.get("/api/runs")
async def runs():
    return hub.history()


@app.get("/api/runs/{run_id}")
async def run_json(run_id: str):
    run = hub.runs.get(run_id)
    if run:
        return {**run.summary(), "events": run.events}
    f = RUNS_DIR / f"{Path(run_id).name}.json"
    if f.exists():
        return JSONResponse(json.loads(f.read_text(encoding="utf-8")))
    raise HTTPException(404, "Unknown run")


@app.get("/api/runs/{run_id}/stream")
async def stream(run_id: str):
    run = hub.runs.get(run_id)
    if not run:
        raise HTTPException(404, "Unknown run")

    def sse(ev: dict) -> str:
        return f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"

    async def gen():
        q: asyncio.Queue = asyncio.Queue()
        run.subscribers.add(q)
        try:
            last = -1
            for ev in list(run.events):  # replay what already happened
                last = ev["i"]
                yield sse(ev)
            while not (run.done and q.empty()):
                try:
                    ev = await asyncio.wait_for(q.get(), 15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if ev["i"] <= last:
                    continue
                last = ev["i"]
                yield sse(ev)
                if ev["type"] == "run.end":
                    break
        finally:
            run.subscribers.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/reports/{name}")
async def report(name: str):
    f = REPORTS_DIR / Path(name).name
    if not f.exists() or f.suffix != ".md":
        raise HTTPException(404, "Report not found")
    return JSONResponse({"name": f.name, "text": f.read_text(encoding="utf-8")})


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"UI: http://{config.HOST}:{config.UI_PORT}")
    uvicorn.run(app, host=config.HOST, port=config.UI_PORT, log_level="warning")


if __name__ == "__main__":
    main()

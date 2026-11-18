# Agentic AI with Google ADK + A2A + MCP (100% local, CPU only)

Three small local models (Hugging Face GGUF, served by Ollama) work as separate **A2A agents**.
Each agent uses **two MCP services**. An orchestrator makes them collaborate.

```
                         You  (python chat.py)
                          |
                 Orchestrator (Google ADK)
                          |   A2A protocol over HTTP
        +-----------------+------------------+
        |                 |                  |
 researcher_agent    analyst_agent      writer_agent
 Qwen3 4B  :9001     Llama 3.2 3B :9002 Qwen2.5 3B :9003
   |        |          |        |         |        |
 duckduckgo fetch    facts_db  time     reports  text_tools      <- MCP servers (stdio)
 (web search)(read   (SQLite)  (clock)  (save .md)(slug, word
             pages)                                 count)
        \_____________________ Ollama (localhost:11434) _____________________/
```

| Agent | Model | MCP service 1 | MCP service 2 |
|---|---|---|---|
| researcher_agent | Qwen3 4B | `duckduckgo` - search the web | `fetch` - read a web page |
| analyst_agent | Llama 3.2 3B | `facts_db` - SQLite database (our own server) | `time` - clock |
| writer_agent | Qwen2.5 3B | `reports` - save/read .md files (our own server) | `text_tools` - slug + word count (our own server) |

Orchestrator modes:
- **pipeline** (default): researcher -> analyst -> writer, always in this order. Most reliable with small models.
- **router**: a small LLM sends your message to ONE specialist (for example "show stored facts" -> analyst).

## 1. Setup (Anaconda Prompt, Windows)

```bat
cd adk_a2a_mcp
pip install -r requirements.txt
```

Open a **separate** window and start Ollama (leave it open). These two settings let all three models stay in RAM:

```bat
set OLLAMA_MAX_LOADED_MODELS=3
set OLLAMA_KEEP_ALIVE=30m
ollama serve
```

Back in the project window, check everything:

```bat
python check_setup.py
```

It must show `[ OK ]` everywhere. If a model name shows `FAIL`, run `ollama list` and copy the exact name into `config.py`.

## 2. Run

One command starts the three agents **and** the web UI, then opens your browser:

```bat
python run_all.py
```

Then use the UI at **http://127.0.0.1:8765**: type a topic, press Enter.
(CPU inference is slow, so a full pipeline run takes a few minutes. Click **Warm up models** first to load all three models into RAM before a demo.)

Other ways to use it:

```bat
python run_all.py --no-ui                                  # agents only
python chat.py                                             # command-line chat (needs run_all.py running)
python chat.py --once "electric vehicles in Pakistan"      # one request, then exit
python chat.py --mode router                               # LLM picks one specialist per message
```

Results: reports go to `reports/`, facts to `data/facts.db`, saved traces to `runs/`, process logs to `logs/`.

## 2b. The web UI (what to show your instructor)

The page answers "what is actually happening?" without clutter. Everything detailed is one click away.

| Area | What it shows |
|---|---|
| **Status line + clock** | One sentence describing the current moment, e.g. "Analyst is calling save_facts on MCP - facts_db" |
| **Flow map** | You -> Orchestrator -> Researcher -> Analyst -> Writer -> Output. Active agent glows, edges animate while an A2A call is in flight, each agent shows its model and its MCP services (chips light up when used, with call counts). Click an agent to filter the trace to it. |
| **Trace** | Every step in order, with start time, duration and a mini timeline bar: pre-flight checks, A2A discovery and hops, MCP connections, every LLM call, every MCP tool call. Filter by LLM / MCP / A2A / Issues. |
| **Result tab** | Final answer, the saved report (rendered), a "where the time went" bar (LLM vs MCP tools vs overhead), time per agent, token counts, and an Export button for the full trace as JSON. |
| **Step tab** | Click any trace row: the exact prompt and system instruction the model saw, tokens and speed, the tool arguments the model chose, the raw tool result, the A2A JSON-RPC request, task states, and how any error was handled. |
| **Agents tab** | Each agent's live A2A "agent card", model, whether the model is in RAM, and MCP tools. |
| **History** | Every run is saved; reopen any past run (great for a demo without waiting). |

Error handling you can demonstrate (all visible in the UI):
- **Pre-flight check**: if Ollama or an agent is down, the run stops immediately with a clear message.
- **Soft failure**: a tool that "succeeds" but returns nothing (e.g. DuckDuckGo "no results") is flagged amber; the Researcher then falls back to Wikipedia.
- **Hard tool failure**: an MCP error is caught, shown red, and returned to the model so it can adapt.
- **Stage failure**: if an agent's model crashes, the pipeline **stops at that stage** (later agents are not run on bad input) and the failure is shown in the flow map, the banner and the trace.
- **Stop button** cancels a running pipeline.

How it works: each agent reports what it does (prompts, LLM timings, MCP calls) to the UI server through `telemetry.py`
in a background thread; the UI server runs the orchestrator itself, records the A2A traffic, and streams everything
to the browser over Server-Sent Events. If the UI is not running, the agents behave exactly the same.
Set `TELEMETRY=0` to switch tracing off completely. One run at a time (agent events are attributed to the active run).

## 3. Project map

| File | Purpose |
|---|---|
| `config.py` | Model names, ports, how each MCP server starts. **Edit models here.** |
| `specialists/*.py` | The three agents: model + instructions + MCP tools, exposed with `to_a2a()` |
| `mcp_servers/*.py` | Our three MCP servers (SQLite facts, reports, text tools) |
| `orchestrator.py` | `RemoteA2aAgent` proxies + `SequentialAgent` / router |
| `run_all.py` | Starts the 3 A2A servers + the web UI and waits until they respond |
| `ui_server.py` | Web UI backend: runs the orchestrator, records A2A traffic, streams the live trace (FastAPI + SSE) |
| `ui/index.html` | The whole web UI in one file (no build step, works offline) |
| `telemetry.py` | Live tracing hooks for the agents (LLM calls, MCP calls, errors) |
| `chat.py` | Command-line chat (shows every tool call and agent hand-off, stops cleanly if a stage fails) |
| `check_setup.py` | Verifies packages, Ollama, tool support, and all MCP servers |

You can inspect an agent's A2A "business card" in the browser: `http://127.0.0.1:9001/.well-known/agent-card.json`

## 4. Troubleshooting

- **`Cannot reach Ollama`** - start `ollama serve` in its own window first.
- **A model "does NOT support tool calling"** - its chat template has no tool section. Pick another model in
  `config.py` (or set `MODEL_WRITER=...` etc.). Check with `ollama show <model>`: "tools" must be under Capabilities.
- **Agent loops or ignores tools** - the model prefix must be `ollama_chat/` (already set in `config.py`). Small models
  also do better with short instructions: edit the `INSTRUCTION` text in `specialists/*.py`.
- **Qwen3 prints long thinking text / is very slow** - the researcher instruction starts with `/no_think` to switch
  thinking off. If it still thinks, set `MODEL_RESEARCHER` to the Qwen2.5 model.
- **`search` returns an error or no results** - DuckDuckGo may rate-limit or block. The researcher is told to fall back
  to a Wikipedia page. Wait a minute and retry, and check your internet connection.
- **Timeouts** - raise `A2A_TIMEOUT` or `MCP_TIMEOUT` (environment variables, see `config.py`).
- **Port already in use** - another `run_all.py` is still running; close it (Ctrl+C) or change the ports in `config.py` (UI port: `UI_PORT`).
- **UI shows an agent as offline** - open `logs/<agent>.log`. If only one agent crashed the others keep running; restart with `python run_all.py`.
- **Trace stays empty but the run works** - the agents could not reach the UI server; make sure you started everything with `run_all.py` (not `--no-ui`).
- **Out of memory** - close other apps, lower `NUM_CTX` (for example `set NUM_CTX=4096`), or set `OLLAMA_MAX_LOADED_MODELS=1`.

## 5. Ideas to extend (for your report / viva)

- Swap in other MCP servers: filesystem, Wikipedia, GitHub, Google Calendar (see `SERVERS` in `config.py`).
- Add a 4th agent (for example a "critic" that reviews the report) - copy `specialists/writer.py`, add a port, add it to `orchestrator.py`.
- Add `tool_filter` lists to give each model even fewer tools if it makes mistakes.
- Evaluate: time per agent, tool-call success rate, report quality for 5 topics.

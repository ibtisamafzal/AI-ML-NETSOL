"""The orchestrator: talks to the three specialist agents over the A2A protocol.

Two modes (set with --mode in chat.py or the ORCHESTRATOR_MODE variable):

  pipeline (default)  SequentialAgent: researcher -> analyst -> writer, always in that order.
                      No model is needed to decide the order, so it is the most reliable
                      choice for small CPU-only models.
  router              A small LLM reads your request and hands it to ONE specialist
                      (e.g. "what is in my database?" -> analyst_agent).

The three specialists must already be running (python run_all.py).
"""
import os

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

import config
import telemetry


class StageFailedError(RuntimeError):
    """A remote agent reported that its task FAILED."""

    def __init__(self, agent: str, message: str):
        super().__init__(f"{agent} failed: {message}")
        self.agent = agent
        self.detail = message


class CheckedRemoteA2aAgent(RemoteA2aAgent):
    """RemoteA2aAgent that stops the pipeline when the remote task fails.

    Plain ADK reports a failed A2A task as an ordinary message and the next agent just carries on
    with bad input. Here a failed task raises StageFailedError instead, so the run stops at the stage
    that broke (the web UI and chat.py both show which one).
    """

    async def _run_async_impl(self, ctx):
        async for event in super()._run_async_impl(ctx):
            yield event
            response = (event.custom_metadata or {}).get("a2a:response") or {}
            status = response.get("status") or {}
            state = str(status.get("state", "")).upper()
            if "FAILED" in state or "REJECTED" in state:
                parts = (status.get("message") or {}).get("parts") or []
                text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                raise StageFailedError(self.name, text or state)


def _remote(name: str, port: int, description: str, httpx_client=None) -> RemoteA2aAgent:
    """A proxy for an agent that lives in another process; every call goes over A2A/HTTP.

    `httpx_client` is optional: the web UI passes one that records the A2A traffic.
    """
    return CheckedRemoteA2aAgent(
        name=name,
        description=description,
        agent_card=f"http://{config.HOST}:{port}{AGENT_CARD_WELL_KNOWN_PATH}",
        timeout=config.A2A_TIMEOUT,
        httpx_client=httpx_client,
    )


def build_orchestrator(mode: str = "pipeline", httpx_client=None):
    researcher = _remote(
        "researcher_agent", config.PORT_RESEARCHER,
        "Searches the web and reads pages to collect facts about a topic.", httpx_client,
    )
    analyst = _remote(
        "analyst_agent", config.PORT_ANALYST,
        "Stores research facts in a database, lists stored facts, and produces key insights.", httpx_client,
    )
    writer = _remote(
        "writer_agent", config.PORT_WRITER,
        "Writes a Markdown report and saves it to a file; can also list and read saved reports.", httpx_client,
    )

    if mode == "router":
        return LlmAgent(
            name="router_agent",
            model=config.make_llm(config.MODEL_ROUTER),
            description="Routes a request to the right specialist agent.",
            instruction=(
                "You are a router. Never answer the question yourself. "
                "Transfer the request to exactly one agent:\n"
                "- researcher_agent: look up or search for information on the web\n"
                "- analyst_agent: save facts, show stored facts, or analyse findings\n"
                "- writer_agent: write, save, list or read reports"
            ),
            sub_agents=[researcher, analyst, writer],
            generate_content_config=config.gen_config(max_tokens=200),
            **telemetry.callbacks("router_agent", config.MODEL_ROUTER),
        )

    return SequentialAgent(
        name="research_pipeline",
        description="Research a topic, analyse and store the facts, then write a report.",
        sub_agents=[researcher, analyst, writer],
    )


root_agent = build_orchestrator(os.environ.get("ORCHESTRATOR_MODE", "pipeline"))

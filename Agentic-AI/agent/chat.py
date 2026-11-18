"""Command-line chat with the orchestrator.

    python chat.py                      # pipeline mode: research -> analyse -> write report
    python chat.py --mode router        # an LLM picks ONE specialist per message
    python chat.py --once "solar energy in Pakistan"   # single question, then exit
"""
import argparse
import asyncio
import sys
import time
import warnings

warnings.filterwarnings("ignore")  # hide library deprecation/experimental noise

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from orchestrator import StageFailedError, build_orchestrator

APP_NAME = "a2a_mcp_demo"
USER_ID = "student"


async def ask(runner: Runner, session_id: str, text: str) -> None:
    message = types.Content(role="user", parts=[types.Part(text=text)])
    started = time.time()
    try:
        async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=message):
            if not event.content or not event.content.parts:
                continue
            for part in event.content.parts:
                if getattr(part, "function_call", None):
                    print(f"\n[{event.author}] -> calling tool/agent: {part.function_call.name}")
                elif getattr(part, "text", None) and not getattr(part, "thought", False):
                    print(f"\n[{event.author}] ({time.time() - started:.0f}s)\n{part.text.strip()}")
    except StageFailedError as exc:
        print(f"\n[FAILED] Pipeline stopped at {exc.agent}: {exc.detail}")
        print("Later agents were NOT run. Check logs/ and that Ollama is running, then try again.")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[FAILED] {type(exc).__name__}: {exc}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["pipeline", "router"], default="pipeline")
    parser.add_argument("--once", metavar="TEXT", help="run one request and exit")
    args = parser.parse_args()

    runner = Runner(
        app_name=APP_NAME,
        agent=build_orchestrator(args.mode),
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )
    session_id = "session-1"

    print(f"Orchestrator ready (mode: {args.mode}). Models run on CPU, so each step can take a minute or more.")
    if args.once:
        await ask(runner, session_id, args.once)
        return
    print("Type a topic or request. Type 'quit' to exit.")
    while True:
        try:
            text = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"quit", "exit", "q"}:
            break
        if text:
            await ask(runner, session_id, text)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # avoid Windows console crashes
    asyncio.run(main())

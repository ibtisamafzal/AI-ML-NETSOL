"""Starts everything: the three specialist A2A servers (researcher, analyst, writer) and the web UI.

    python run_all.py              start agents + UI and open the browser
    python run_all.py --no-ui      only the three agents (use chat.py in a second window)
    python run_all.py --no-browser start the UI but do not open the browser

Press Ctrl+C to stop everything. Every process writes its log to ./logs/<name>.log.
If one agent crashes the others keep running, and the UI shows that agent as offline.
"""
import argparse
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser

import config

AGENTS = [
    ("researcher", "specialists.researcher:app", config.PORT_RESEARCHER),
    ("analyst", "specialists.analyst:app", config.PORT_ANALYST),
    ("writer", "specialists.writer:app", config.PORT_WRITER),
]
CARD_PATH = "/.well-known/agent-card.json"


def is_up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _stop(*_args):
    raise KeyboardInterrupt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ui", action="store_true", help="do not start the web UI")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args()

    import importlib.util  # every agent is started with THIS Python, so it must be the one that has the packages
    missing = [m for m in ("google.adk", "mcp", "litellm", "fastapi", "uvicorn", "httpx",
                           "duckduckgo_mcp_server", "mcp_server_fetch", "mcp_server_time")
               if importlib.util.find_spec(m.split(".")[0]) is None]
    if missing:
        print(f"[FAIL] This Python is missing packages: {', '.join(missing)}")
        print(f"       Python used: {sys.executable}")
        print("       Start with the virtual environment's Python:  python run_all.py   (NOT: py run_all.py)")
        print("       To install the packages:  python -m pip install -r requirements.txt")
        return 1

    signal.signal(signal.SIGTERM, _stop)  # so `kill` / closing the window also stops everything cleanly
    log_dir = config.ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    procs: list[tuple[str, str, subprocess.Popen]] = []  # (name, url to probe, process)

    def launch(name: str, cmd: list[str], probe: str) -> None:
        log = open(log_dir / f"{name}.log", "w", encoding="utf-8")
        procs.append((name, probe, subprocess.Popen(cmd, cwd=config.ROOT, stdout=log, stderr=subprocess.STDOUT)))

    try:
        for name, target, port in AGENTS:
            launch(name, [sys.executable, "-m", "uvicorn", target, "--host", config.HOST, "--port", str(port)],
                   f"http://{config.HOST}:{port}{CARD_PATH}")
        ui_url = f"http://{config.HOST}:{config.UI_PORT}"
        if not args.no_ui:
            launch("ui", [sys.executable, "ui_server.py"], ui_url + "/api/status")

        for name, probe, proc in procs:
            for _ in range(90):
                if proc.poll() is not None:
                    print(f"[FAIL] {name} stopped. See logs/{name}.log")
                    return 1
                if is_up(probe):
                    print(f"[ OK ] {name:<10} {probe.split('/.well-known')[0].split('/api')[0]}")
                    break
                time.sleep(1)
            else:
                print(f"[FAIL] {name} did not start in 90s. See logs/{name}.log")
                return 1

        if args.no_ui:
            print("\nAgents are running. In a second terminal run:  python chat.py")
        else:
            print(f"\nOpen the UI:  {ui_url}")
            if not args.no_browser:
                webbrowser.open(ui_url)
        print("Press Ctrl+C here to stop everything.")

        reported: set[str] = set()
        while True:
            time.sleep(1)
            for name, _probe, proc in procs:
                if proc.poll() is not None and name not in reported:
                    reported.add(name)
                    print(f"[WARN] {name} stopped unexpectedly (see logs/{name}.log). The others keep running.")
    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        for _name, _probe, proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for _name, _probe, proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
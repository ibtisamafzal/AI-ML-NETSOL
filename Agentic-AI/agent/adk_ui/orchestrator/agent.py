"""Lets you use the orchestrator in ADK's web UI:  adk web adk_ui   (run from the project folder)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # make config.py importable

from orchestrator import root_agent  # noqa: E402,F401

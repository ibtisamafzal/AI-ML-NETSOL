"""MCP server #2 (used by the Writer): saves and reads Markdown reports in the ./reports folder.

Tools:
  save_report(filename, content)
  list_reports()
  read_report(filename)
Only the ./reports folder is reachable, so a confused model cannot touch other files.
"""
import os
import re
from pathlib import Path

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as Server

REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", Path(__file__).resolve().parent.parent / "reports"))

mcp = Server("reports")


def _safe_name(filename: str) -> str:
    name = Path(filename.strip()).name  # drop any folder parts
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.") or "report"
    return name if name.lower().endswith(".md") else name + ".md"


@mcp.tool()
def save_report(filename: str, content: str) -> str:
    """Save a Markdown report to disk.

    Args:
        filename: File name such as "solar-energy.md".
        content: The full Markdown text of the report.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / _safe_name(filename)
    path.write_text(content, encoding="utf-8")
    return f"Saved report to {path} ({len(content.split())} words)."


@mcp.tool()
def list_reports() -> str:
    """List all saved reports."""
    if not REPORTS_DIR.exists():
        return "No reports yet."
    files = sorted(p.name for p in REPORTS_DIR.glob("*.md"))
    return "\n".join(files) if files else "No reports yet."


@mcp.tool()
def read_report(filename: str) -> str:
    """Read a saved report.

    Args:
        filename: Name of the report file, as shown by list_reports.
    """
    path = REPORTS_DIR / _safe_name(filename)
    if not path.exists():
        return f"Report '{path.name}' not found."
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run()  # stdio

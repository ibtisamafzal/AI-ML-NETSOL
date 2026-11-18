"""MCP server #3 (used by the Writer): small text helpers.

Tools:
  make_slug(title)   - "Solar Energy in Pakistan!" -> "solar-energy-in-pakistan"
  word_count(text)   - number of words
"""
import re

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as Server

mcp = Server("text-tools")


@mcp.tool()
def make_slug(title: str) -> str:
    """Turn a title into a file-name-friendly slug (lowercase, words joined by dashes).

    Args:
        title: The report title.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60] or "report"


@mcp.tool()
def word_count(text: str) -> str:
    """Count the words in a text.

    Args:
        text: Any text.
    """
    return f"{len(text.split())} words"


if __name__ == "__main__":
    mcp.run()  # stdio

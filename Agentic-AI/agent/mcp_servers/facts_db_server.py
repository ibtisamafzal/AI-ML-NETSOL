"""MCP server #1 (used by the Analyst): a tiny SQLite "facts" database.

Tools:
  save_facts(topic, facts)  - store facts (plain text, one per line)
  list_facts(topic)         - read stored facts back
Runs over stdio, so it is started automatically by the agent -- you never start it by hand.
"""
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as Server

DB_PATH = Path(os.environ.get("FACTS_DB", Path(__file__).resolve().parent.parent / "data" / "facts.db"))

mcp = Server("facts-db")

# Lines that are agent-to-agent wrapper text, not facts. Small models sometimes paste the whole
# quoted transcript into `facts`; we skip those lines so they never reach the database.
_NOISE = re.compile(
    r"QUOTED_AGENT_CONTENT|transcript of what another agent did|^\[\w+\]\s.*\bsaid\b|^For context:|tool returned result",
    re.IGNORECASE,
)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS facts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT, fact TEXT, source TEXT, saved_at TEXT)"
    )
    return conn


@mcp.tool()
def save_facts(topic: str, facts: str) -> str:
    """Save facts into the local database.

    Args:
        topic: Short topic name, for example "solar energy in Pakistan".
        facts: The facts as plain text, ONE FACT PER LINE. A source URL may be at the end of a line.
    """
    topic = topic.strip().lower()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    saved = 0
    with closing(_connect()) as conn:
        for line in facts.splitlines():
            line = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s*", "", line).strip()
            if len(line) < 5 or _NOISE.search(line) or line.lower() == topic:
                continue
            if conn.execute("SELECT 1 FROM facts WHERE topic = ? AND fact = ?", (topic, line)).fetchone():
                continue  # already stored
            match = re.search(r"https?://\S+", line)
            source = match.group(0).rstrip(").,") if match else ""
            conn.execute(
                "INSERT INTO facts (topic, fact, source, saved_at) VALUES (?, ?, ?, ?)",
                (topic, line, source, now),
            )
            saved += 1
        conn.commit()
    return f"Saved {saved} facts under topic '{topic}'."


@mcp.tool()
def list_facts(topic: str = "") -> str:
    """List stored facts. Leave topic empty to list the latest facts of every topic.

    Args:
        topic: Topic name to filter by (partial match is fine).
    """
    topic = topic.strip().lower()
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT topic, fact, source FROM facts WHERE topic LIKE ? ORDER BY id DESC LIMIT 30",
            (f"%{topic}%",),
        ).fetchall()
    if not rows:
        return "No facts stored yet."
    lines = [f"{i}. [{t}] {f}" for i, (t, f, _s) in enumerate(rows, 1)]
    sources = {s for _t, _f, s in rows if s}
    return f"{len(rows)} facts, {len(sources)} distinct sources:\n" + "\n".join(lines)


if __name__ == "__main__":
    mcp.run()  # stdio

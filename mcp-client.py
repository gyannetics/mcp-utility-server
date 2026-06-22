"""
MCP Test Client for Daily Utilities Server
==========================================

Demonstrates how to connect to an MCP server from Python using the official
``mcp`` SDK — without Cursor or Claude Desktop in the loop.

Connection modes
----------------
**stdio (default)**
    Spawns ``server.py`` as a child process and talks over stdin/stdout.
    This mirrors how desktop AI hosts launch local MCP servers.

**SSE (``--sse URL``)**
    Connects to a server already running in HTTP/SSE mode
    (``uv run server.py sse``). Useful for remote or integration testing.

Usage
-----
::

    uv run mcp-client.py
    uv run mcp-client.py --tool get_motivational_quote
    uv run mcp-client.py --sse http://localhost:8000/sse

Architecture
------------
1. Open a transport (``stdio_client`` or ``sse_client``).
2. Wrap streams in a :class:`mcp.client.session.ClientSession`.
3. Call ``session.initialize()`` to perform the MCP handshake.
4. Discover tools with ``session.list_tools()``.
5. Invoke tools with ``session.call_tool(name, arguments)``.

Note: The MCP Python SDK does **not** expose a high-level ``Client`` class;
the session + transport pattern shown here is the supported approach.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult

# Absolute path to this repo — used to spawn server.py with a stable cwd.
PROJECT_DIR = Path(__file__).resolve().parent

# Network-backed tools (quotes, jokes) may need extra time for API fallbacks.
NETWORK_TOOL_TIMEOUT = timedelta(seconds=30)


@dataclass(frozen=True)
class ToolDemo:
    """
    Configuration for a single tool invocation in the demo runner.

    Attributes
    ----------
    name:
        MCP tool name as registered on the server (e.g. ``"get_dad_joke"``).
    arguments:
        JSON-serializable argument dict, or ``None`` for parameterless tools.
    label:
        Human-readable label printed in demo output.
    uses_network:
        When True, ``call_tool`` uses an extended read timeout because the
        server may contact external HTTP APIs (with its own fallbacks).
    """

    name: str
    arguments: dict | None
    label: str
    uses_network: bool = False


# Demo sequence exercised when no ``--tool`` filter is provided.
# Targets ``server.py``; adapt this list if testing ``server1.py`` instead.
TOOL_DEMOS: tuple[ToolDemo, ...] = (
    ToolDemo("get_current_datetime", None, "Current Time"),
    ToolDemo("add_numbers", {"a": 42, "b": 17}, "Addition (42 + 17)"),
    ToolDemo("multiply_numbers", {"a": 6, "b": 7}, "Multiplication (6 × 7)"),
    ToolDemo("safe_calculate", {"expression": "15 * 7 + 22"}, "Calculation (15 * 7 + 22)"),
    ToolDemo(
        "get_motivational_quote",
        None,
        "Motivational Quote (internet, with fallbacks)",
        uses_network=True,
    ),
    ToolDemo("get_dad_joke", None, "Dad Joke (internet, with fallbacks)", uses_network=True),
)


def tool_text(result: CallToolResult) -> str:
    """
    Extract displayable text from an MCP tool call result.

    FastMCP tools may return content blocks and/or structured JSON. This
    helper normalizes both shapes for console output.

    Parameters
    ----------
    result:
        Raw :class:`~mcp.types.CallToolResult` from ``session.call_tool``.

    Returns
    -------
    str
        Text representation of the tool output.

    Raises
    ------
    RuntimeError
        If the server marked the result as an error (``isError=True``).
    """
    if result.isError:
        raise RuntimeError(result.content[0].text if result.content else "Tool call failed")
    if result.structuredContent and "result" in result.structuredContent:
        return str(result.structuredContent["result"])
    if result.content and hasattr(result.content[0], "text"):
        return result.content[0].text
    return str(result)


async def call_tool(session: ClientSession, demo: ToolDemo) -> CallToolResult:
    """
    Invoke one demo tool, applying a longer timeout for network tools.

    Parameters
    ----------
    session:
        Initialized MCP client session.
    demo:
        Tool name, arguments, and timeout metadata.

    Returns
    -------
    CallToolResult
        Unprocessed MCP tool response.
    """
    kwargs: dict = {}
    if demo.uses_network:
        kwargs["read_timeout_seconds"] = NETWORK_TOOL_TIMEOUT
    return await session.call_tool(demo.name, demo.arguments, **kwargs)


async def list_tools(session: ClientSession) -> None:
    """
    Print all tools advertised by the server after initialization.

    Parameters
    ----------
    session:
        Initialized MCP client session.
    """
    tools_result = await session.list_tools()
    print("Available Tools:")
    for tool in tools_result.tools:
        desc = (tool.description or "").replace("\n", " ")
        preview = desc[:80]
        suffix = "..." if len(desc) > 80 else ""
        print(f"   • {tool.name} - {preview}{suffix}")


async def run_tool_demos(session: ClientSession, demos: tuple[ToolDemo, ...]) -> None:
    """
    Run a sequence of tool demos and print each result.

    Parameters
    ----------
    session:
        Initialized MCP client session.
    demos:
        One or more :class:`ToolDemo` entries to execute in order.
    """
    print("\n" + "=" * 60 + "\n")
    print("Testing Tools:\n")

    for demo in demos:
        if demo.uses_network:
            print(f"Fetching {demo.label}...")
        result = await call_tool(session, demo)
        print(f"{demo.label}: {tool_text(result)}")
        print()


async def run_session(session: ClientSession, tool_name: str | None = None) -> None:
    """
    Full client workflow: handshake, list tools, run demo(s).

    Parameters
    ----------
    session:
        Connected but not yet initialized MCP client session.
    tool_name:
        If provided, run only the matching demo from :data:`TOOL_DEMOS`.
        Otherwise run the full demo suite.

    Raises
    ------
    SystemExit
        If ``tool_name`` does not match any configured demo tool.
    """
    await session.initialize()
    await list_tools(session)

    if tool_name:
        demo = next((item for item in TOOL_DEMOS if item.name == tool_name), None)
        if demo is None:
            available = ", ".join(item.name for item in TOOL_DEMOS)
            raise SystemExit(f"Unknown tool '{tool_name}'. Available demo tools: {available}")
        await run_tool_demos(session, (demo,))
    else:
        await run_tool_demos(session, TOOL_DEMOS)

    print("All done!")


async def main_stdio(tool_name: str | None) -> None:
    """
    Connect to ``server.py`` by spawning it as a child process (stdio).

    Parameters
    ----------
    tool_name:
        Optional single-tool filter forwarded to :func:`run_session`.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(PROJECT_DIR / "server.py")],
        cwd=str(PROJECT_DIR),
    )
    print("Connecting to MCP server via stdio...\n")
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await run_session(session, tool_name)


async def main_sse(url: str, tool_name: str | None) -> None:
    """
    Connect to an already-running SSE MCP server.

    Parameters
    ----------
    url:
        Full SSE endpoint, typically ``http://localhost:8000/sse``.
    tool_name:
        Optional single-tool filter forwarded to :func:`run_session`.
    """
    print(f"Connecting to MCP server at {url}...\n")
    async with sse_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await run_session(session, tool_name)


def parse_args() -> argparse.Namespace:
    """Parse CLI flags for transport selection and single-tool mode."""
    parser = argparse.ArgumentParser(description="Test client for Daily Utilities MCP server")
    parser.add_argument(
        "--sse",
        metavar="URL",
        default=None,
        help="Connect via SSE (e.g. http://localhost:8000/sse). Start server with: python server.py sse",
    )
    parser.add_argument(
        "--tool",
        metavar="NAME",
        default=None,
        help="Call a single tool instead of running the full demo",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.sse:
        asyncio.run(main_sse(args.sse, args.tool))
    else:
        asyncio.run(main_stdio(args.tool))

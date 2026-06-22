"""
MCP Client Example - Talk to your Daily Utilities Server

Usage:
  python mcp-client.py                                    # stdio (spawns server.py locally)
  python mcp-client.py --sse http://localhost:8000/sse    # remote SSE (run server.py sse first)
  python mcp-client.py --tool get_motivational_quote      # call a single tool
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

PROJECT_DIR = Path(__file__).resolve().parent
NETWORK_TOOL_TIMEOUT = timedelta(seconds=30)


@dataclass(frozen=True)
class ToolDemo:
    name: str
    arguments: dict | None
    label: str
    uses_network: bool = False


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
    if result.isError:
        raise RuntimeError(result.content[0].text if result.content else "Tool call failed")
    if result.structuredContent and "result" in result.structuredContent:
        return str(result.structuredContent["result"])
    if result.content and hasattr(result.content[0], "text"):
        return result.content[0].text
    return str(result)


async def call_tool(
    session: ClientSession,
    demo: ToolDemo,
) -> CallToolResult:
    kwargs: dict = {}
    if demo.uses_network:
        kwargs["read_timeout_seconds"] = NETWORK_TOOL_TIMEOUT
    return await session.call_tool(demo.name, demo.arguments, **kwargs)


async def list_tools(session: ClientSession) -> None:
    tools_result = await session.list_tools()
    print("Available Tools:")
    for tool in tools_result.tools:
        desc = (tool.description or "").replace("\n", " ")
        preview = desc[:80]
        suffix = "..." if len(desc) > 80 else ""
        print(f"   • {tool.name} - {preview}{suffix}")


async def run_tool_demos(session: ClientSession, demos: tuple[ToolDemo, ...]) -> None:
    print("\n" + "=" * 60 + "\n")
    print("Testing Tools:\n")

    for demo in demos:
        if demo.uses_network:
            print(f"Fetching {demo.label}...")
        result = await call_tool(session, demo)
        print(f"{demo.label}: {tool_text(result)}")
        print()


async def run_session(session: ClientSession, tool_name: str | None = None) -> None:
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
    print(f"Connecting to MCP server at {url}...\n")
    async with sse_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await run_session(session, tool_name)


def parse_args() -> argparse.Namespace:
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

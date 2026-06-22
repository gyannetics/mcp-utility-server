"""
Daily Utilities MCP Server
==========================

Core Model Context Protocol (MCP) server exposing everyday utility tools
for AI clients such as Cursor and Claude Desktop.

Transports
----------
- **stdio** (default): Local process communication used by desktop AI apps.
  Run with ``uv run server.py`` or ``python server.py``.
- **SSE** (optional): HTTP Server-Sent Events for remote deployment.
  Run with ``uv run server.py sse`` (requires the ``sse`` extra).

Tools exposed
-------------
- ``get_current_datetime`` — formatted local date/time
- ``add_numbers`` / ``multiply_numbers`` — basic arithmetic
- ``safe_calculate`` — AST-based math evaluator (no ``eval()``)
- ``get_motivational_quote`` — internet quotes with provider fallbacks
- ``get_dad_joke`` — jokes from icanhazdadjoke.com with local fallbacks

Design notes
------------
- FastMCP auto-generates JSON schemas from type hints and docstrings.
- All logging goes to **stderr** so stdout remains clean for stdio MCP.
- FastAPI/uvicorn are imported lazily so stdio mode works without the
  ``sse`` optional dependency group installed.

See README.md for Cursor/Claude configuration and client usage.
"""

import ast
import datetime
import logging
import operator
import random
import sys
import traceback
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging — MUST use stderr in stdio transport (stdout is the MCP wire protocol)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP server instance — name appears in client UIs (Cursor, Claude, etc.)
# ---------------------------------------------------------------------------
mcp = FastMCP("Daily Utilities 🚀")

# ---------------------------------------------------------------------------
# Safe calculator — whitelist AST node types instead of using eval()
# ---------------------------------------------------------------------------
ALLOWED_OPERATORS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


def _safe_eval(node: ast.AST) -> float:
    """
    Recursively evaluate a restricted AST subtree containing only numbers
    and basic binary/unary arithmetic operators.

    Parameters
    ----------
    node:
        Root AST node produced by ``ast.parse(..., mode="eval")``.

    Returns
    -------
    float
        Numeric result of the expression.

    Raises
    ------
    ValueError
        If the node contains disallowed types, non-numeric constants,
        unsupported operators, or division by zero.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("Only numbers allowed")
    if isinstance(node, ast.BinOp):
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        op_type = type(node.op)
        if op_type in ALLOWED_OPERATORS:
            if op_type == ast.Div and right == 0:
                raise ValueError("Division by zero")
            return ALLOWED_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported operator: {op_type}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_eval(node.operand)
    raise ValueError(f"Unsupported expression type: {type(node)}")


# ---------------------------------------------------------------------------
# MCP tools — sync and async handlers discovered automatically by FastMCP
# ---------------------------------------------------------------------------

@mcp.tool()
def get_current_datetime() -> str:
    """
    Return the current local date and time in a human-readable format.

    Returns
    -------
    str
        Example: ``"Sunday, June 21, 2026 — 04:00:50 PM"``.
    """
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y — %I:%M:%S %p")


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """
    Add two numbers.

    Parameters
    ----------
    a:
        First addend.
    b:
        Second addend.

    Returns
    -------
    float
        Sum ``a + b``.
    """
    return a + b


@mcp.tool()
def multiply_numbers(a: float, b: float) -> float:
    """
    Multiply two numbers.

    Parameters
    ----------
    a:
        First factor.
    b:
        Second factor.

    Returns
    -------
    float
        Product ``a * b``.
    """
    return a * b


@mcp.tool()
def safe_calculate(expression: str) -> str:
    """
    Safely evaluate a basic math expression without calling ``eval()``.

    Supported syntax: ``+``, ``-``, ``*``, ``/``, ``**``, parentheses, and
    unary minus. Only numeric literals are permitted.

    Parameters
    ----------
    expression:
        Math expression to evaluate, e.g. ``"15 * 7 + 22"`` or ``"(10 * 3) / 2"``.

    Returns
    -------
    str
        Result string like ``"15 * 7 + 22 = 127.0"``, or an error message
        describing what went wrong.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {str(e)}. Try something like '2 + 2' or '(5 * 3) / 2'."


# ---------------------------------------------------------------------------
# Motivational quotes — multi-provider HTTP fetch with offline fallbacks
# ---------------------------------------------------------------------------
FALLBACK_QUOTES: list[str] = [
    "The only way to do great work is to love what you do. — Steve Jobs",
    "Success is not final, failure is not fatal: it is the courage to continue that counts. — Winston Churchill",
    "The future belongs to those who believe in the beauty of their dreams. — Eleanor Roosevelt",
    "It always seems impossible until it's done. — Nelson Mandela",
    "Everything you've ever wanted is sitting on the other side of fear. — Jack Canfield",
]

_HTTP_HEADERS: dict[str, str] = {
    "Accept": "application/json",
    "User-Agent": "MCP-Daily-Utilities/1.0",
}
_HTTP_TIMEOUT: float = 15.0


def _format_quote(content: str, author: str | None) -> str:
    """
    Normalize API quote payloads into a single display string.

    Parameters
    ----------
    content:
        Quote body text from an external API.
    author:
        Optional author name; appended after an em dash when present.

    Returns
    -------
    str
        Formatted quote, e.g. ``"Quote text — Author Name"``.

    Raises
    ------
    ValueError
        If ``content`` is empty after stripping whitespace.
    """
    content = content.strip()
    if not content:
        raise ValueError("Empty quote content")
    if author and author.strip():
        return f"{content} — {author.strip()}"
    return content


async def _fetch_quote_from_quotable(client: httpx.AsyncClient) -> str:
    """
    Fetch one random inspirational quote from quotable.io.

    Parameters
    ----------
    client:
        Shared async HTTP client (connection pooling, shared headers).

    Returns
    -------
    str
        Formatted quote string.

    Raises
    ------
    httpx.HTTPError
        On network or HTTP status failures.
    ValueError
        If the response body is missing expected fields.
    """
    response = await client.get(
        "https://api.quotable.io/random",
        params={"tags": "inspirational|motivational|success|wisdom"},
    )
    response.raise_for_status()
    data = response.json()
    return _format_quote(data.get("content", ""), data.get("author"))


async def _fetch_quote_from_zenquotes(client: httpx.AsyncClient) -> str:
    """
    Fetch one random quote from zenquotes.io (backup provider).

    Parameters
    ----------
    client:
        Shared async HTTP client.

    Returns
    -------
    str
        Formatted quote string.

    Raises
    ------
    httpx.HTTPError
        On network or HTTP status failures.
    ValueError
        If the JSON shape is not a non-empty list of quote objects.
    """
    response = await client.get("https://zenquotes.io/api/random")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Unexpected zenquotes response shape")
    entry = data[0]
    return _format_quote(entry.get("q", ""), entry.get("a"))


async def fetch_motivational_quote() -> str:
    """
    Fetch a motivational quote with ordered provider fallbacks.

    Attempts quotable.io first, then zenquotes.io. If every provider fails,
    returns a random entry from :data:`FALLBACK_QUOTES`.

    Returns
    -------
    str
        A motivational quote string, always non-empty.
    """
    providers = (
        ("quotable.io", _fetch_quote_from_quotable),
        ("zenquotes.io", _fetch_quote_from_zenquotes),
    )

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS) as client:
        for name, fetcher in providers:
            try:
                quote = await fetcher(client)
                logger.info("Fetched motivational quote from %s", name)
                return quote
            except Exception as e:
                logger.warning("Motivational quote fetch failed (%s): %s", name, e)

    logger.info("Using local fallback motivational quote")
    return random.choice(FALLBACK_QUOTES)


@mcp.tool()
async def get_motivational_quote() -> str:
    """
    Return a random motivational quote fetched from the internet.

    Uses :func:`fetch_motivational_quote` under the hood. Falls back to
    bundled quotes when external APIs are unreachable.

    Returns
    -------
    str
        Motivational quote, typically including an author attribution.
    """
    return await fetch_motivational_quote()


@mcp.tool()
async def get_dad_joke() -> str:
    """
    Fetch a random dad joke from icanhazdadjoke.com.

    Returns
    -------
    str
        Joke text from the API, or a random local fallback joke if the
        network request fails.
    """
    url = "https://icanhazdadjoke.com/"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            joke = data.get("joke")
            if joke:
                return joke
    except Exception as e:
        logger.error("Dad joke fetch failed: %s", e)

    fallbacks = [
        "Why don't skeletons fight each other? They don't have the guts.",
        "I'm reading a book about anti-gravity. It's impossible to put down!",
        "Why did the scarecrow win an award? Because he was outstanding in his field!",
        "Why don't eggs tell jokes? They'd crack each other up.",
    ]
    return random.choice(fallbacks)


# ---------------------------------------------------------------------------
# Remote SSE deployment (optional — requires ``uv sync --extra sse``)
# ---------------------------------------------------------------------------
def create_sse_app():
    """
    Build a FastAPI application that exposes this MCP server over SSE.

    The MCP SSE app is mounted at ``/`` so clients connect to
    ``http://<host>:8000/sse``.

    Returns
    -------
    fastapi.FastAPI
        ASGI app suitable for uvicorn.

    Notes
    -----
    Imports FastAPI lazily so stdio-only installs do not require the
    ``sse`` dependency group.
    """
    from fastapi import FastAPI
    from starlette.middleware.cors import CORSMiddleware

    app = FastAPI(title="Daily Utilities MCP Server")

    # Permissive CORS for local development / remote clients.
    # Tighten ``allow_origins`` before production deployment.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/", mcp.sse_app())
    return app


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def main() -> None:
    """
    Start the MCP server in stdio transport mode.

    This is the mode used by Cursor, Claude Desktop, and ``mcp-client.py``.
    Blocks until the parent process closes the connection.
    """
    logger.info("=== Daily Utilities MCP Server STARTING (stdio) ===")
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error("CRITICAL ERROR: %s", e)
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    # ``python server.py``       → stdio (local MCP clients)
    # ``python server.py sse``   → HTTP/SSE on port 8000
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        import uvicorn

        logger.info("Starting SSE server for remote access on http://0.0.0.0:8000")
        uvicorn.run(create_sse_app(), host="0.0.0.0", port=8000)
    else:
        main()

"""
Daily Utilities MCP Server
- Local: stdio (Claude Desktop)
- Remote: SSE / HTTP (deployable)
"""

import datetime
import random
import logging
import sys
import ast
import operator
import traceback
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ====================== MCP SERVER ======================
mcp = FastMCP("Daily Utilities 🚀")

# ====================== SAFE CALCULATOR ======================
ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

def _safe_eval(node: ast.AST) -> float:
    """Safely evaluate simple math expressions."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("Only numbers allowed")
    elif isinstance(node, ast.BinOp):
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        op_type = type(node.op)
        if op_type in ALLOWED_OPERATORS:
            if op_type == ast.Div and right == 0:
                raise ValueError("Division by zero")
            return ALLOWED_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported operator: {op_type}")
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_eval(node.operand)
    else:
        raise ValueError(f"Unsupported expression type: {type(node)}")


# ====================== TOOLS ======================

@mcp.tool()
def get_current_datetime() -> str:
    """Returns the current date and time in a friendly format."""
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y — %I:%M:%S %p")


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Adds two numbers."""
    return a + b


@mcp.tool()
def multiply_numbers(a: float, b: float) -> float:
    """Multiplies two numbers."""
    return a * b


@mcp.tool()
def safe_calculate(expression: str) -> str:
    """
    Safely evaluates a basic math expression.
    Examples: "2 + 2", "(10 * 3) / 2", "2 ** 8"
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {str(e)}. Try something like '2 + 2' or '(5 * 3) / 2'."


FALLBACK_QUOTES = [
    "The only way to do great work is to love what you do. — Steve Jobs",
    "Success is not final, failure is not fatal: it is the courage to continue that counts. — Winston Churchill",
    "The future belongs to those who believe in the beauty of their dreams. — Eleanor Roosevelt",
    "It always seems impossible until it's done. — Nelson Mandela",
    "Everything you've ever wanted is sitting on the other side of fear. — Jack Canfield",
]

_HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "MCP-Daily-Utilities/1.0",
}
_HTTP_TIMEOUT = 15.0


def _format_quote(content: str, author: str | None) -> str:
    content = content.strip()
    if not content:
        raise ValueError("Empty quote content")
    if author and author.strip():
        return f"{content} — {author.strip()}"
    return content


async def _fetch_quote_from_quotable(client: httpx.AsyncClient) -> str:
    """Fetch a random quote from quotable.io."""
    response = await client.get(
        "https://api.quotable.io/random",
        params={"tags": "inspirational|motivational|success|wisdom"},
    )
    response.raise_for_status()
    data = response.json()
    return _format_quote(data.get("content", ""), data.get("author"))


async def _fetch_quote_from_zenquotes(client: httpx.AsyncClient) -> str:
    """Fetch a random quote from zenquotes.io."""
    response = await client.get("https://zenquotes.io/api/random")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Unexpected zenquotes response shape")
    entry = data[0]
    return _format_quote(entry.get("q", ""), entry.get("a"))


async def fetch_motivational_quote() -> str:
    """
    Fetch a motivational quote from the internet with provider fallbacks.

    Tries quotable.io first, then zenquotes.io, then local fallbacks.
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
    """Returns a random motivational quote fetched from the internet."""
    return await fetch_motivational_quote()


@mcp.tool()
async def get_dad_joke() -> str:
    """Fetches a random dad joke from the internet."""
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
        logger.error(f"Dad joke fetch failed: {e}")
    
    # Fallbacks
    fallbacks = [
        "Why don't skeletons fight each other? They don't have the guts.",
        "I'm reading a book about anti-gravity. It's impossible to put down!",
        "Why did the scarecrow win an award? Because he was outstanding in his field!",
        "Why don't eggs tell jokes? They'd crack each other up."
    ]
    return random.choice(fallbacks)


# ====================== REMOTE SSE SUPPORT ======================
def create_sse_app():
    """Create FastAPI app for remote SSE deployment."""
    from fastapi import FastAPI
    from starlette.middleware.cors import CORSMiddleware

    app = FastAPI(title="Daily Utilities MCP Server")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.mount("/", mcp.sse_app())
    return app


# ====================== ENTRY POINT ======================
def main():
    """Local stdio mode (Claude Desktop)."""
    logger.info("=== Daily Utilities MCP Server STARTING (stdio) ===")
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {e}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        import uvicorn

        logger.info("Starting SSE server for remote access on http://0.0.0.0:8000")
        uvicorn.run(create_sse_app(), host="0.0.0.0", port=8000)
    else:
        main()
"""
Daily Utilities Pro MCP Server
==============================

Extended MCP server that layers optional AI capabilities on top of the
basic daily-utility tools.

Feature tiers
-------------
**Always available (no API key):**
- Date/time, quotes, dad jokes
- Sandboxed file listing and reading
- Simple prompt enhancement helper

**Requires ``langchain`` extra** (``uv sync --extra langchain``):
- ``web_search`` — DuckDuckGo via LangChain Community
- ``ask_smart`` — tool-calling agent with per-session memory

**Requires API key in ``.env``:**
- ``OPENAI_API_KEY`` and/or ``GROQ_API_KEY`` enable the smart agent.
- Groq is preferred when both keys are present.

Transports
----------
- **stdio** (default): ``uv run server1.py``
- **SSE / Docker**: ``uv run server1.py sse`` (requires ``sse`` extra)
  Health probe: ``GET /health`` — MCP clients use ``/sse``.

Security
--------
File tools restrict access to the project working directory, the user's
Documents folder, and Downloads folder. Files larger than 500 KB cannot
be read; returned content is capped at 8 000 characters.

See README.md for setup, dependency extras, and client configuration.
"""

import datetime
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load OPENAI_API_KEY / GROQ_API_KEY from a local .env file (not committed).
load_dotenv()

# ---------------------------------------------------------------------------
# Logging — stderr only (stdout reserved for MCP stdio wire protocol)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP("Daily Utilities Pro 🚀")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")

# Template for future on-disk session persistence (not fully wired yet).
MEMORY_FILE_TEMPLATE = "memory_{session}.json"

# In-process conversation memory keyed by session id (e.g. "default").
memories: dict[str, Any] = {}

# Directories the file tools are allowed to touch (resolved absolute paths).
ALLOWED_ROOTS: tuple[Path, ...] = (
    Path.cwd(),
    Path.home() / "Documents",
    Path.home() / "Downloads",
)

# File read limits — protect against large/binary file abuse.
MAX_FILE_BYTES = 500_000
MAX_READ_CHARS = 8_000
MAX_DIR_ENTRIES = 50

_HTTP_HEADERS: dict[str, str] = {"Accept": "application/json"}
_HTTP_TIMEOUT: float = 10.0


def _is_allowed_path(path: Path) -> bool:
    """
    Return True if ``path`` resolves inside one of :data:`ALLOWED_ROOTS`.

    Parameters
    ----------
    path:
        Already-resolved absolute path to check.

    Returns
    -------
    bool
        Whether read/list operations are permitted on this path.
    """
    return any(path.is_relative_to(root) for root in ALLOWED_ROOTS)


# ---------------------------------------------------------------------------
# Basic tools — no external API keys required
# ---------------------------------------------------------------------------

@mcp.tool()
def get_current_datetime() -> str:
    """
    Return the current local date and time.

    Returns
    -------
    str
        Human-readable timestamp, e.g. ``"Sunday, June 21, 2026 — 04:00:50 PM"``.
    """
    return datetime.datetime.now().strftime("%A, %B %d, %Y — %I:%M:%S %p")


@mcp.tool()
def get_motivational_quote() -> str:
    """
    Return a random motivational quote from a built-in list.

    Returns
    -------
    str
        Static inspirational quote (no network call). See ``server.py`` for
        the internet-backed version with API fallbacks.
    """
    quotes = [
        "The only way to do great work is to love what you do. — Steve Jobs",
        "Success is not final, failure is not fatal: it is the courage to continue that counts.",
        "Everything you've ever wanted is sitting on the other side of fear.",
    ]
    return random.choice(quotes)


@mcp.tool()
async def get_dad_joke() -> str:
    """
    Fetch a random dad joke from icanhazdadjoke.com.

    Returns
    -------
    str
        Joke text from the API, or a programming-themed fallback on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS) as client:
            resp = await client.get("https://icanhazdadjoke.com/")
            resp.raise_for_status()
            data = resp.json()
            return data.get("joke", "No joke available right now.")
    except Exception as e:
        logger.warning("Dad joke fetch failed: %s", e)
        return "Why do programmers prefer dark mode? Because light attracts bugs."


# ---------------------------------------------------------------------------
# File tools — sandboxed to ALLOWED_ROOTS
# ---------------------------------------------------------------------------

@mcp.tool()
def list_directory(path: str = ".") -> str:
    """
    List files and subdirectories inside an allowed folder.

    Parameters
    ----------
    path:
        Directory path relative to the current working directory or absolute.
        Must resolve under project cwd, Documents, or Downloads.

    Returns
    -------
    str
        Newline-separated listing (directories suffixed with ``/``), or an
        error message if access is denied or the path is invalid.
    """
    try:
        resolved = Path(path).resolve()
        if not _is_allowed_path(resolved):
            return "Error: Directory access not allowed for security."
        items = [f.name + ("/" if f.is_dir() else "") for f in resolved.iterdir()]
        return f"Contents of {resolved}:\n" + "\n".join(items[:MAX_DIR_ENTRIES])
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def read_file(path: str) -> str:
    """
    Read a text file from an allowed location.

    Parameters
    ----------
    path:
        File path to read. Must resolve under an allowed root directory.

    Returns
    -------
    str
        File contents (UTF-8, invalid bytes ignored), truncated to
        :data:`MAX_READ_CHARS` characters, or an error message.
    """
    try:
        resolved = Path(path).resolve()
        if not _is_allowed_path(resolved):
            return "Error: File access not allowed for security."
        if resolved.stat().st_size > MAX_FILE_BYTES:
            return "Error: File too large (>500KB)."
        return resolved.read_text(encoding="utf-8", errors="ignore")[:MAX_READ_CHARS]
    except Exception as e:
        return f"Error reading file: {str(e)}"


# ---------------------------------------------------------------------------
# Web search & prompt helper
# ---------------------------------------------------------------------------

@mcp.tool()
def web_search(query: str) -> str:
    """
    Search the web using DuckDuckGo (via LangChain Community).

    Parameters
    ----------
    query:
        Natural-language search query.

    Returns
    -------
    str
        Search result snippets, or a message if LangChain/DDG is unavailable.

    Notes
    -----
    Requires ``uv sync --extra langchain`` (installs ``duckduckgo-search``).
    """
    try:
        from langchain_community.tools.ddg_search import DuckDuckGoSearchRun

        return DuckDuckGoSearchRun().run(query)
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return "Web search temporarily unavailable."


@mcp.tool()
def enhance_prompt(original_prompt: str) -> str:
    """
    Return a lightly structured revision of a user prompt.

    This is a deterministic template helper, not an LLM call. It reminds
    the caller to add context, examples, and output format constraints.

    Parameters
    ----------
    original_prompt:
        Raw prompt text to improve.

    Returns
    -------
    str
        Original prompt wrapped with improvement guidance.
    """
    return (
        f"Improved prompt:\n{original_prompt}\n\n"
        "(Add more context, examples, and desired format for better results.)"
    )


# ---------------------------------------------------------------------------
# Optional LangChain agent — registered only when an API key is present
# ---------------------------------------------------------------------------
if OPENAI_API_KEY or GROQ_API_KEY:
    try:
        from langchain.agents import AgentExecutor, create_tool_calling_agent
        from langchain.memory import ConversationBufferMemory
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.tools import tool
        from langchain_groq import ChatGroq
        from langchain_openai import ChatOpenAI

        @tool
        def ask_smart(question: str, session: str = "default") -> str:
            """
            Answer a question using an LLM agent with optional web search.

            Parameters
            ----------
            question:
                User question or task description.
            session:
                Conversation session id. Memory is isolated per session
                for the lifetime of the server process.

            Returns
            -------
            str
                Agent response text, or an error message on failure.

            Notes
            -----
            - Uses Groq (``llama-3.1-70b-versatile``) when ``GROQ_API_KEY`` is set.
            - Falls back to OpenAI (``gpt-4o-mini``) otherwise.
            - The agent may call :func:`web_search` as a tool mid-reasoning.
            """
            try:
                memory = memories.setdefault(
                    session,
                    ConversationBufferMemory(return_messages=True),
                )

                if GROQ_API_KEY:
                    llm = ChatGroq(
                        model="llama-3.1-70b-versatile",
                        temperature=0.7,
                        groq_api_key=GROQ_API_KEY,
                    )
                else:
                    llm = ChatOpenAI(
                        model="gpt-4o-mini",
                        temperature=0.7,
                        openai_api_key=OPENAI_API_KEY,
                    )

                prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a helpful assistant."),
                    ("placeholder", "{chat_history}"),
                    ("human", "{input}"),
                ])

                agent = create_tool_calling_agent(llm, [web_search], prompt)
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=[web_search],
                    verbose=True,
                    memory=memory,
                )

                result = agent_executor.invoke({"input": question})
                return result["output"]
            except Exception as e:
                logger.error("Smart assistant error: %s", e)
                return f"Smart assistant error: {str(e)}"

        mcp.add_tool(ask_smart)
        logger.info("LangChain smart agent enabled (Groq/OpenAI)")
    except Exception as e:
        logger.warning("LangChain initialization failed: %s", e)
else:
    logger.info(
        "No OPENAI_API_KEY or GROQ_API_KEY found — ask_smart tool not registered"
    )


# ---------------------------------------------------------------------------
# Remote SSE deployment (optional — requires ``uv sync --extra sse``)
# ---------------------------------------------------------------------------
def create_sse_app():
    """
    Build a FastAPI app that serves this MCP server over SSE.

    Returns
    -------
    fastapi.FastAPI
        ASGI application for uvicorn.

    Notes
    -----
    FastAPI is imported lazily so stdio mode works without the ``sse`` extra.
    """
    from fastapi import FastAPI
    from starlette.middleware.cors import CORSMiddleware

    app = FastAPI(title="Daily Utilities Pro")

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """
        Liveness probe for load balancers, orchestrators, and Docker HEALTHCHECK.

        Returns a small JSON payload so callers can verify the HTTP process is
        up without opening an MCP session.
        """
        return {
            "status": "healthy",
            "server": "daily-utilities-pro",
            "transport": "sse",
        }

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/", mcp.sse_app())
    return app


def run_sse() -> None:
    """
    Start the MCP server in SSE/HTTP mode (default for Docker deployments).

    Host and port are read from ``HOST`` (default ``0.0.0.0``) and ``PORT``
    (default ``8000``). Health checks should target ``GET /health``.
    """
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting SSE server on http://%s:%s (health: /health)", host, port)
    uvicorn.run(create_sse_app(), host=host, port=port)


def main() -> None:
    """
    Start the MCP server in stdio transport mode.

    Blocks until the host application (Cursor, Claude, etc.) closes stdin.
    """
    logger.info("=== Daily Utilities Pro MCP Server STARTING (stdio) ===")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    # ``python server1.py``       → stdio (local MCP clients)
    # ``python server1.py sse``   → HTTP/SSE on port 8000 (+ ``GET /health``)
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        run_sse()
    else:
        main()

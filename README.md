# MCP Utility Server

A beginner-friendly **Model Context Protocol (MCP)** project in Python with two server implementations:

| File | Description |
|------|-------------|
| `server.py` | Core MVP — time, math, internet quotes, dad jokes |
| `server1.py` | Pro server — file tools, web search, optional LangChain agent (OpenAI / Groq) |

Includes a test client (`mcp-client.py`) and support for **stdio** (local) and **SSE** (remote) transports.

## What is MCP?

**Model Context Protocol** is an open standard that lets AI applications (Cursor, Claude Desktop, VS Code, custom agents, etc.) connect to external tools and data in a standardized way.

Your MCP server exposes **Tools** (actions the AI can call). This project focuses on tools.

## Tools

### `server.py` — Daily Utilities

| Tool | Description | Type |
|------|-------------|------|
| `get_current_datetime` | Current date and time, formatted | Sync |
| `add_numbers` | Adds two numbers | Sync |
| `multiply_numbers` | Multiplies two numbers | Sync |
| `safe_calculate` | Safely evaluates math expressions (no `eval`) | Sync |
| `get_motivational_quote` | Fetches a quote from the internet (with fallbacks) | Async |
| `get_dad_joke` | Fetches a dad joke from [icanhazdadjoke.com](https://icanhazdadjoke.com) | Async |

### `server1.py` — Daily Utilities Pro

Includes the basic tools above, plus:

| Tool | Description |
|------|-------------|
| `list_directory` | Lists files in allowed directories (project, Documents, Downloads) |
| `read_file` | Reads a text file (size-limited, sandboxed) |
| `web_search` | DuckDuckGo web search (requires `langchain` extra) |
| `enhance_prompt` | Simple prompt improvement helper |
| `ask_smart` | LangChain agent with session memory (requires API key + `langchain` extra) |

## Quick Start

### Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) (recommended)

### Install

```bash
git clone https://github.com/gyannetics/mcp-utility-server.git
cd mcp-utility-server

# Core dependencies only (server.py)
uv sync

# All features (server1.py, SSE, LangChain)
uv sync --all-extras
```

### Optional dependency groups

| Extra | Packages | Used by |
|-------|----------|---------|
| *(core)* | `mcp`, `httpx`, `python-dotenv` | Both servers |
| `sse` | `fastapi`, `uvicorn` | Remote SSE mode |
| `langchain` | LangChain, OpenAI/Groq, DuckDuckGo search | `server1.py` agent & web search |
| `all` | Everything above | Full Pro setup |

```bash
uv sync --extra sse
uv sync --extra langchain
```

### Environment variables (`server1.py`)

Copy `.env` and add your keys (at least one for the smart agent):

```env
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk-...
```

Groq is preferred when both keys are set. Basic tools work without any API key.

## Run the Server

### Stdio (local — Claude Desktop, Cursor)

```bash
uv run server.py
# or
uv run server1.py
```

The server waits for MCP connections over stdin/stdout.

### SSE (remote)

```bash
uv run server.py sse
# Server available at http://localhost:8000
```

Requires the `sse` extra (`uv sync --extra sse`).

## Test with the MCP Client

```bash
# Full demo via stdio (spawns server.py automatically)
uv run mcp-client.py

# Test a single tool
uv run mcp-client.py --tool get_motivational_quote

# Connect to a running SSE server
uv run server.py sse
uv run mcp-client.py --sse http://localhost:8000/sse
```

## Use with Cursor

1. Open **Cursor Settings** → **Tools & MCP** → **Add MCP Server**
2. Or edit `%USERPROFILE%\.cursor\mcp.json` (Windows) / `~/.cursor/mcp.json` (macOS/Linux):

```json
{
  "mcpServers": {
    "daily-utilities": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\ABSOLUTE\\PATH\\TO\\mcp-utility-server",
        "run",
        "server.py"
      ]
    }
  }
}
```

Use the **full absolute path** to this project. Reload Cursor after saving.

Example prompts:

- "What time is it?"
- "Calculate 15 * 7 + 22"
- "Tell me a dad joke"
- "Give me a motivational quote"

## Use with Claude Desktop

1. Open Claude Desktop → **Settings** → **Developer** → **Edit Config**
2. Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "daily-utilities": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/mcp-utility-server",
        "run",
        "server.py"
      ]
    }
  }
}
```

3. Fully quit and restart Claude Desktop.

## Project Structure

```
mcp-utility-server/
├── server.py           # Core MCP server
├── server1.py          # Pro server with LangChain agent
├── mcp-client.py       # Test client (stdio + SSE)
├── pyproject.toml      # Dependencies and optional extras
├── .env                # API keys (not committed)
├── .gitignore
└── README.md
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Server not appearing in Cursor/Claude | Check absolute path in config; reload or restart the app |
| `ImportError` for `fastapi` / `langchain` | Run `uv sync --all-extras` |
| `Client` import error in `mcp-client.py` | Use the project venv: `uv run mcp-client.py` |
| Quotes/jokes time out | Network tools use a 30s timeout; check internet access |
| stdout errors in stdio mode | Never use `print()` — log to stderr with `logging` |
| pip conflicts in Anaconda | Use this project's `.venv` via `uv sync`, not global `pip` |

**Cursor MCP logs:** View → Output → select **MCP** from the dropdown.

**Claude Desktop logs (macOS):** `~/Library/Logs/Claude/mcp*.log`

## Learning & Resources

This project demonstrates:

- Building MCP servers with **FastMCP**
- Auto-generated tool schemas from type hints and docstrings
- Sync vs async tools
- Safe HTTP calls with fallbacks
- Optional LangChain agent integration
- Stdio and SSE transports
- A Python MCP client using `ClientSession`

### Extend it

1. Add **Resources** — expose files or data as readable context
2. Add **Prompts** — reusable prompt templates
3. Persist data — todo lists, notes, session history to disk
4. Deploy remotely — SSE on Railway, Fly.io, or similar
5. Connect more APIs — Notion, GitHub, databases, etc.

### Official links

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Build an MCP Server (tutorial)](https://modelcontextprotocol.io/docs/develop/build-server)
- [Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Awesome MCP Servers](https://github.com/punkpeye/awesome-mcp-servers)

---

Built as an educational MCP starter. Experiment, extend, and have fun.

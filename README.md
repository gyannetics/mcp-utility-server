# Daily Utilities MCP Server (MVP)

A beginner-friendly **Model Context Protocol (MCP)** server built in Python.

This project serves as a complete, runnable MVP to help you learn how to build MCP servers.

## What is MCP?

**Model Context Protocol** is an open standard that lets AI applications (Claude, Cursor, VS Code, custom agents, etc.) connect to external tools, data, and workflows in a standardized, secure way.

Think of it as **"USB-C for AI"**.

Your MCP server exposes **Tools** (actions the AI can call), **Resources** (data it can read), and **Prompts** (templates).

This MVP focuses on **Tools**.

## Features (Tools) Included

| Tool                    | Description                                      | Type     |
|-------------------------|--------------------------------------------------|----------|
| `get_current_datetime`  | Returns current date & time nicely formatted     | Sync     |
| `add_numbers`           | Adds two numbers                                 | Sync     |
| `multiply_numbers`      | Multiplies two numbers                           | Sync     |
| `safe_calculate`        | Safely evaluates math expressions (no `eval`!)   | Sync     |
| `get_motivational_quote`| Returns a random inspirational quote             | Sync     |
| `get_dad_joke`          | Fetches a real dad joke from the internet        | **Async** |

## Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- [`uv`](https://docs.astral.sh/uv/) (recommended) or pip

### 2. Setup

```bash
# Clone or download this folder
cd mcp-utility-server

# Create virtual environment and install dependencies
uv sync
# or: pip install -e .
```

### 3. Run the Server (for testing)

```bash
uv run server.py
```

You should see it start (it will wait for connections via stdio).

### 4. Use with Claude Desktop (Recommended)

1. Open Claude Desktop → Settings → Developer → Edit Config
2. Add your server to `claude_desktop_config.json`:

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

**Important:** Use the **full absolute path** to this folder.

3. Fully quit and restart Claude Desktop.
4. Start a new chat and try:
   - "What time is it right now?"
   - "Calculate 15 * 7 + 22"
   - "Tell me a dad joke"
   - "Give me some motivation"

Claude will automatically discover your tools and ask for permission before using them.

## Project Structure

```
mcp-utility-server/
├── pyproject.toml      # Project config + dependencies
├── server.py           # The actual MCP server (well commented!)
└── README.md           # This file
```

## Learning Path & Next Steps

### What you learned in this MVP:
- Using `FastMCP` (the easiest way to build MCP servers in Python)
- The power of **type hints + docstrings** (FastMCP uses them to auto-generate tool schemas)
- Sync vs Async tools
- Safe external API calls
- Proper logging for stdio servers

### Ideas to extend this server:
1. **Add Resources** — Expose a local file or database as readable context.
2. **Add Prompts** — Create reusable prompt templates (e.g., "Weekly Review Prompt").
3. **Persist data** — Make a todo list tool that saves to a JSON file.
4. **Add authentication** — For remote servers.
5. **Deploy remotely** — Use SSE transport + deploy to Railway, Fly.io, or AWS Lambda.
6. **Connect to real APIs** — Gmail, Notion, your company's internal tools, databases, etc.

### Official Resources
- [Model Context Protocol Official Site](https://modelcontextprotocol.io/)
- [Build an MCP Server (Official Tutorial)](https://modelcontextprotocol.io/docs/develop/build-server)
- [Python SDK on GitHub](https://github.com/modelcontextprotocol/python-sdk)
- [Awesome MCP Servers](https://github.com/punkpeye/awesome-mcp-servers)

## Troubleshooting

- **Server not appearing in Claude?** → Check absolute path in config + fully restart Claude.
- **Logs**: Check `~/Library/Logs/Claude/mcp*.log` (macOS)
- **Error about stdout?** → Never use `print()` — always log to stderr (we use `logging` in this project).

---

Built as an educational MVP. Have fun extending it!

Questions? Feel free to experiment and break things — that's how you learn MCP.

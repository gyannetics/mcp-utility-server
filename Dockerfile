# Daily Utilities Pro MCP Server — SSE mode for container/remote deployments.
# Default entrypoint: server1.py (LangChain + file tools + basic utilities).

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
RUN uv sync --all-extras --no-dev --no-install-project

# Application source (server1.py is the default runtime target).
COPY server.py server1.py mcp-client.py ./

# ---------------------------------------------------------------------------
# Runtime image
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=8000

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/server.py /app/server1.py /app/mcp-client.py /app/README.md ./

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

# SSE transport — MCP clients connect to http://<host>:8000/sse
CMD ["python", "server1.py", "sse"]

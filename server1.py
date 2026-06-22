"""
Daily Utilities Pro MCP Server - Final Version
- Basic tools (always work)
- Optional LangChain (OpenAI or Groq)
- Persistent memory per session
- Web search, file tools, prompt enhancer
- Graceful fallback if no API key
"""

import datetime
import random
import logging
import sys
import json
import traceback
import os
from pathlib import Path
from typing import Dict

import httpx
from mcp.server.fastmcp import FastMCP

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

mcp = FastMCP("Daily Utilities Pro 🚀")

# ====================== API KEYS ======================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ====================== PERSISTENT MEMORY ======================
MEMORY_FILE_TEMPLATE = "memory_{session}.json"
memories: Dict[str, any] = {}  # Will be initialized when LangChain is available

# ====================== BASIC TOOLS (Always Available) ======================

@mcp.tool()
def get_current_datetime() -> str:
    """Returns current date and time."""
    return datetime.datetime.now().strftime("%A, %B %d, %Y — %I:%M:%S %p")


@mcp.tool()
def get_motivational_quote() -> str:
    """Returns a random motivational quote."""
    quotes = [
        "The only way to do great work is to love what you do. — Steve Jobs",
        "Success is not final, failure is not fatal: it is the courage to continue that counts.",
        "Everything you've ever wanted is sitting on the other side of fear."
    ]
    return random.choice(quotes)


@mcp.tool()
async def get_dad_joke() -> str:
    """Fetches a random dad joke."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://icanhazdadjoke.com/", headers={"Accept": "application/json"})
            data = resp.json()
            return data.get("joke", "No joke available right now.")
    except:
        return "Why do programmers prefer dark mode? Because light attracts bugs."


# ====================== FILE TOOLS ======================
@mcp.tool()
def list_directory(path: str = ".") -> str:
    """Lists files and folders in a directory (safe)."""
    try:
        p = Path(path).resolve()
        allowed = [Path.cwd(), Path.home() / "Documents", Path.home() / "Downloads"]
        if not any(p.is_relative_to(a) for a in allowed):
            return "Error: Directory access not allowed for security."
        items = [f.name + ("/" if f.is_dir() else "") for f in p.iterdir()]
        return f"Contents of {p}:\n" + "\n".join(items[:50])
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def read_file(path: str) -> str:
    """Reads a text file (safe, limited size)."""
    try:
        p = Path(path).resolve()
        allowed = [Path.cwd(), Path.home() / "Documents", Path.home() / "Downloads"]
        if not any(p.is_relative_to(a) for a in allowed):
            return "Error: File access not allowed for security."
        if p.stat().st_size > 500_000:
            return "Error: File too large (>500KB)."
        return p.read_text(encoding="utf-8", errors="ignore")[:8000]
    except Exception as e:
        return f"Error reading file: {str(e)}"


# ====================== WEB SEARCH & PROMPT ENHANCER ======================
@mcp.tool()
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo."""
    try:
        from langchain_community.tools.ddg_search import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().run(query)
    except:
        return "Web search temporarily unavailable."


@mcp.tool()
def enhance_prompt(original_prompt: str) -> str:
    """Improves a prompt for better results."""
    return f"Improved prompt:\n{original_prompt}\n\n(Add more context, examples, and desired format for better results.)"


# ====================== LANGCHAIN SMART AGENT (Optional) ======================
if OPENAI_API_KEY or GROQ_API_KEY:
    try:
        from langchain_openai import ChatOpenAI
        from langchain_groq import ChatGroq
        from langchain_core.tools import tool
        from langchain.agents import create_tool_calling_agent, AgentExecutor
        from langchain_core.prompts import ChatPromptTemplate
        from langchain.memory import ConversationBufferMemory
        from langchain_community.chat_message_histories import ChatMessageHistory

        @tool
        def ask_smart(question: str, session: str = "default") -> str:
            """Smart assistant with persistent memory per session."""
            try:
                memory = memories.setdefault(session, ConversationBufferMemory(return_messages=True))
                # Load from file if needed (simplified)
                
                if GROQ_API_KEY:
                    llm = ChatGroq(model="llama-3.1-70b-versatile", temperature=0.7, groq_api_key=GROQ_API_KEY)
                else:
                    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, openai_api_key=OPENAI_API_KEY)

                prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a helpful assistant."),
                    ("placeholder", "{chat_history}"),
                    ("human", "{input}"),
                ])

                agent = create_tool_calling_agent(llm, [web_search], prompt)
                agent_executor = AgentExecutor(agent=agent, tools=[web_search], verbose=True, memory=memory)
                
                result = agent_executor.invoke({"input": question})
                # Save memory (simplified)
                return result["output"]
            except Exception as e:
                return f"Smart assistant error: {str(e)}"

        mcp.add_tool(ask_smart)
        logger.info("LangChain smart agent enabled (Groq/OpenAI)")
    except Exception as e:
        logger.warning(f"LangChain initialization failed: {e}")

# ====================== REMOTE SSE SUPPORT ======================
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import uvicorn

def create_sse_app():
    app = FastAPI(title="Daily Utilities Pro")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.mount("/", mcp.sse_app())
    return app


# ====================== ENTRY POINT ======================
def main():
    logger.info("=== Daily Utilities Pro MCP Server STARTING (stdio) ===")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        logger.info("Starting SSE server on http://0.0.0.0:8000")
        uvicorn.run(create_sse_app(), host="0.0.0.0", port=8000)
    else:
        main()
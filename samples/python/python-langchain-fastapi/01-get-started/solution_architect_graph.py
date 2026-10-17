"""Build the LangChain Solution Architect graph without runtime dependencies."""

from __future__ import annotations

import os
from typing import Any

from env_loader import ensure_env_loaded
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from mcp_mslearn_tool import mslearn_mcp_search

ensure_env_loaded()

SYSTEM_PROMPT = (
    "You are a Senior AI Solution Architect. "
    "Design production-ready AI architectures, justify tradeoffs, cite Microsoft Learn references, "
    "and provide clear migration and operations guidance. "
    "When documentation is needed, call the mslearn_mcp_search tool first."
)


def build_solution_architect_agent() -> Any:
    """Create the application's native LangChain agent and its MCP tool."""
    model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-5-chat"), temperature=1)
    return create_agent(model=model, tools=[mslearn_mcp_search], system_prompt=SYSTEM_PROMPT)

"""Build the approval-enabled LangGraph without runtime dependencies."""

from __future__ import annotations

import os
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from env_loader import ensure_env_loaded
from mcp_mslearn_tool import mslearn_mcp_search

ensure_env_loaded()

SYSTEM_PROMPT = (
    "You are a Senior AI Solution Architect. "
    "Design production-ready AI architectures, justify tradeoffs, cite Microsoft Learn references, "
    "and provide clear migration and operations guidance. "
    "When documentation is needed, call the mslearn_mcp_search tool first."
)


def build_developer_agent(*, model: Any | None = None) -> Any:
    """Create a LangGraph agent with explicit approve-or-reject tool interrupts."""
    chat_model = model or ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=1)
    return create_agent(
        model=chat_model,
        tools=[mslearn_mcp_search],
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "mslearn_mcp_search": InterruptOnConfig(
                        allowed_decisions=["approve", "reject"]
                    )
                }
            )
        ],
        checkpointer=InMemorySaver(),
    )

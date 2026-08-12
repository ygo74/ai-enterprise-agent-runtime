from __future__ import annotations

import os
from typing import Any

from agent_framework.openai import OpenAIChatClient

from env_loader import ensure_env_loaded
from mcp_mslearn_tool import mslearn_mcp_search

ensure_env_loaded()


SYSTEM_PROMPT = (
    "You are a Senior AI Solution Architect. "
    "Design production-ready AI architectures, justify tradeoffs, cite Microsoft Learn references, "
    "and provide clear migration and operations guidance. "
    "When documentation is needed, call the mslearn_mcp_search tool first."
)


def build_solution_architect_agent() -> Any:
    """Build the Solution Architect Microsoft Agent Framework agent (business logic only).

    This is the only function specific to this agent: model, tools, and instructions. Invocation
    (single-shot vs real token streaming) and inline tool-call notices for chat UIs (e.g. LibreChat)
    are handled generically by `ygo74.agent_runtime.create_agent_framework_entrypoint`, wired in
    `openai_responses_app.py` -- exactly the same runtime helper contract used by the LangChain-based
    `01-get-started` example, proving the library does not depend on any particular agent framework.
    """

    model_name = os.getenv("OPENAI_MODEL", "gpt-5-chat")

    client = OpenAIChatClient(
        model=model_name,
        base_url=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    return client.as_agent(
        name="SolutionArchitect",
        instructions=SYSTEM_PROMPT,
        tools=mslearn_mcp_search,
    )

from __future__ import annotations

import os
from typing import Any

from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from env_loader import ensure_env_loaded
from mcp_mslearn_tool import mslearn_mcp_search

ensure_env_loaded()


SYSTEM_PROMPT = (
    "You are a Senior AI Solution Architect. "
    "Design production-ready AI architectures, justify tradeoffs, cite Microsoft Learn references, "
    "and provide clear migration and operations guidance. "
    "When documentation is needed, call the mslearn_mcp_search tool first."
)

try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent

    _HAS_LEGACY_TOOL_CALLING = True
except Exception:
    AgentExecutor = Any  # type: ignore[assignment]
    create_tool_calling_agent = None
    _HAS_LEGACY_TOOL_CALLING = False


def build_solution_architect_agent() -> Any:
    """Build the Solution Architect LangChain agent (business logic only).

    This is the only function specific to this agent: model, tools, and system prompt.
    Invocation (single-shot vs real token streaming) and inline tool-call notices for
    chat UIs (e.g. LibreChat) are handled generically by
    `ygo74.agent_runtime.create_langchain_agent_entrypoint`, wired in `openai_responses_app.py`.
    """

    model_name = os.getenv("OPENAI_MODEL", "gpt-5-chat")
    llm = ChatOpenAI(model=model_name, temperature=1)
    tools = [mslearn_mcp_search]

    # LangChain <1.0 compatibility path.
    if _HAS_LEGACY_TOOL_CALLING and create_tool_calling_agent is not None:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )
        agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=False)

    # LangChain >=1.0 compatibility path.
    return create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)

from __future__ import annotations

import os
from typing import Any, AsyncIterator

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


def _normalize_agent_output(result: Any) -> str:
    if isinstance(result, dict):
        output = result.get("output")
        if isinstance(output, str) and output:
            return output

        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            content = getattr(last, "content", last)
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    else:
                        parts.append(str(item))
                return "\n".join(part for part in parts if part)
            return str(content)

    return str(result)


async def run_solution_architect_agent(user_input: str) -> dict[str, Any]:
    executor = build_solution_architect_agent()

    if _HAS_LEGACY_TOOL_CALLING:
        result = await executor.ainvoke({"input": user_input})
    else:
        result = await executor.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": user_input,
                    }
                ]
            }
        )

    output = _normalize_agent_output(result)
    return {
        "role": "assistant",
        "content": output,
    }


def _extract_chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", None)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)

    return ""


async def run_solution_architect_agent_stream(user_input: str) -> AsyncIterator[str]:
    """Yield incremental text deltas of the final assistant answer as they are produced.

    Uses astream_events (supported by both the legacy AgentExecutor and the langgraph-based
    create_agent runnable) and only forwards text deltas coming from chat model token streaming,
    filtering out empty chunks (e.g. tool-call-only turns).
    """

    executor = build_solution_architect_agent()

    if _HAS_LEGACY_TOOL_CALLING:
        input_payload: dict[str, Any] = {"input": user_input}
    else:
        input_payload = {"messages": [{"role": "user", "content": user_input}]}

    async for event in executor.astream_events(input_payload, version="v2"):
        if event.get("event") != "on_chat_model_stream":
            continue

        chunk = event.get("data", {}).get("chunk")
        if chunk is None:
            continue

        delta_text = _extract_chunk_text(chunk)
        if delta_text:
            yield delta_text

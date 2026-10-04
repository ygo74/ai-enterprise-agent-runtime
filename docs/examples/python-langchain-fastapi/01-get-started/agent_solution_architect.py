from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import aclosing
from enum import StrEnum
from typing import Any

from env_loader import ensure_env_loaded
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.runnables.schema import StreamEvent
from langchain_openai import ChatOpenAI
from mcp_mslearn_tool import mslearn_mcp_search
from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput, Notification
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEvent,
)
from ygo74.agent_runtime.integrations.langchain import (
    ConversionOutcome,
    LangChainConversionError,
    LangChainResultAdapter,
    LangChainStreamAdapter,
)

ensure_env_loaded()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Senior AI Solution Architect. "
    "Design production-ready AI architectures, justify tradeoffs, cite Microsoft Learn references, "
    "and provide clear migration and operations guidance. "
    "When documentation is needed, call the mslearn_mcp_search tool first."
)


class ArchitectEvent(StrEnum):
    MODEL_STREAM = "on_chat_model_stream"
    MODEL_END = "on_chat_model_end"
    TOOL_START = "on_tool_start"
    TOOL_END = "on_tool_end"


class SolutionArchitect:
    def __init__(self, executor: Any, *, tool_notices: bool) -> None:
        self._executor: Any = executor
        self._tool_notices: bool = tool_notices

    @classmethod
    def configured(cls) -> SolutionArchitect:
        notices = os.getenv("AGENT_STREAM_TOOL_NOTICES", "true").strip().lower() not in ("0", "false", "no")
        return cls(build_solution_architect_agent(), tool_notices=notices)

    async def run(self, user_input: str) -> AgentOutput:
        result = await self._executor.ainvoke({"messages": [{"role": "user", "content": user_input}]})
        # Agent state contains history as well as the answer; select the final
        # assistant message explicitly rather than exposing the whole snapshot.
        messages = result.get("messages", [])
        message = next((item for item in reversed(messages) if isinstance(item, AIMessage)), None)
        if message is None:
            raise LangChainConversionError("The agent returned no assistant answer.")
        outcome = LangChainResultAdapter().convert(message)
        self._diagnose(outcome)
        if outcome.output is None:
            raise LangChainConversionError("The assistant answer could not be converted.")
        return outcome.output

    async def stream(self, user_input: str) -> AsyncIterator[AgentStreamEvent]:
        converter = LangChainStreamAdapter()
        notice_index = 0
        native_events = self._executor.astream_events(
            {"messages": [{"role": "user", "content": user_input}]}, version="v2",
        )
        async with aclosing(native_events):
            async for event in native_events:
                kind = event["event"]
                if kind in (ArchitectEvent.TOOL_START, ArchitectEvent.TOOL_END):
                    if self._tool_notices:
                        notice_index += 1
                        yield ContentEvent(f"tool-notice-{notice_index}", Notification(self._notice(event)))
                    continue
                if kind not in (ArchitectEvent.MODEL_STREAM, ArchitectEvent.MODEL_END):
                    # Inputs, graph snapshots and custom events are intentionally not
                    # output. This selection remains controlled by the developer.
                    continue
                outcome = converter.convert(event)
                self._diagnose(outcome)
                for converted in outcome.events:
                    yield converted
        for converted in converter.finish().events:
            yield converted

    @staticmethod
    def _notice(event: StreamEvent) -> str:
        name = event["name"] or "tool"
        if event["event"] == ArchitectEvent.TOOL_END:
            return f"\n> ✅ _Tool `{name}` completed._\n\n"
        raw_input = event["data"].get("input")
        query = raw_input.get("query") if isinstance(raw_input, dict) else None
        detail = f' — "{query}"' if query else ""
        return f"\n> 🔧 _Calling tool `{name}`{detail}..._\n\n"

    @staticmethod
    def _diagnose(outcome: ConversionOutcome) -> None:
        for diagnostic in outcome.diagnostics:
            logger.info("LangChain output selection: code=%s reason=%s", diagnostic.code, diagnostic.reason)


def build_solution_architect_agent() -> Any:
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-5-chat"), temperature=1)
    return create_agent(model=llm, tools=[mslearn_mcp_search], system_prompt=SYSTEM_PROMPT)


async def run_solution_architect_agent(user_input: str) -> AgentOutput:
    return await SolutionArchitect.configured().run(user_input)


def run_solution_architect_agent_stream(user_input: str) -> AsyncIterator[AgentStreamEvent]:
    return SolutionArchitect.configured().stream(user_input)

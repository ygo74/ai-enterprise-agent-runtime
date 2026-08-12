from __future__ import annotations

import os
from typing import Any, AsyncIterator, Callable, Union

BuildAgent = Union[Callable[[], Any], Any]
"""Either a zero-arg factory returning a fresh agent instance per request, or a
pre-built, reusable agent instance."""


def _resolve_agent(build_agent: BuildAgent) -> Any:
    """Resolve build_agent into a concrete agent instance.

    Supports both a per-request factory (matching the historical example behavior)
    and a reusable pre-built instance, mirroring the LangChain adapter contract.
    """

    if callable(build_agent):
        return build_agent()
    return build_agent


def _extract_user_input(payload: dict[str, Any]) -> str:
    incoming = payload.get("input")

    if isinstance(incoming, list):
        return "\n".join(str(item) for item in incoming)

    return str(incoming)


def _tool_notices_enabled(override: bool | None) -> bool:
    if override is not None:
        return override

    return os.getenv("AGENT_STREAM_TOOL_NOTICES", "true").strip().lower() not in ("0", "false", "no")


def _format_tool_start_notice(tool_name: str) -> str:
    return f"\n> 🔧 _Calling tool `{tool_name}`..._\n\n"


def _format_tool_end_notice(tool_name: str) -> str:
    return f"\n> ✅ _Tool `{tool_name}` completed._\n\n"


async def _run_once(build_agent: BuildAgent, payload: dict[str, Any]) -> dict[str, Any]:
    agent = _resolve_agent(build_agent)
    user_input = _extract_user_input(payload)

    response = await agent.run(user_input)

    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {"role": "assistant", "content": response.text},
        "metadata": {"route_key": payload["route_key"]},
    }


async def _stream(build_agent: BuildAgent, payload: dict[str, Any], notices_enabled: bool) -> AsyncIterator[str]:
    """Yield incremental text deltas of the final assistant answer as they are produced.

    Iterates the framework-native `agent.run(user_input, stream=True)` update stream. Each
    `AgentResponseUpdate` carries a list of `Content` items (duck-typed via a `type`
    discriminator: "text", "function_call", "function_result", ...), so this adapter never
    imports `agent_framework` types directly -- any object exposing this same shape works.
    Tool call notices (rendered as short Markdown blockquotes, same convention as the
    LangChain adapter) are injected directly into the content stream so any OpenAI-compatible
    client (e.g. LibreChat) shows the user that a tool is being called. Set
    AGENT_STREAM_TOOL_NOTICES=false to disable these notices.
    """

    agent = _resolve_agent(build_agent)
    user_input = _extract_user_input(payload)

    tool_names: dict[str, str] = {}

    async for update in agent.run(user_input, stream=True):
        for content in getattr(update, "contents", None) or []:
            content_type = getattr(content, "type", None)

            if content_type == "function_call":
                call_id = getattr(content, "call_id", None)
                if call_id and call_id not in tool_names:
                    tool_names[call_id] = getattr(content, "name", None) or "tool"
                    if notices_enabled:
                        yield _format_tool_start_notice(tool_names[call_id])
                continue

            if content_type == "function_result":
                call_id = getattr(content, "call_id", None)
                if notices_enabled:
                    yield _format_tool_end_notice(tool_names.get(call_id, "tool"))
                continue

        delta_text = getattr(update, "text", None)
        if delta_text:
            yield delta_text


def create_agent_framework_entrypoint(
    build_agent: BuildAgent,
    *,
    tool_notices: bool | None = None,
) -> Callable[[dict[str, Any]], Any]:
    """Wrap a Microsoft Agent Framework agent into an add_ai_endpoints-compatible entrypoint.

    Args:
        build_agent: Either a zero-arg factory returning a fresh agent instance per request
            (an `agent_framework.Agent`, or anything exposing the same `run(...)` contract),
            or a reusable pre-built instance.
        tool_notices: Force-enable/disable inline tool-call notices regardless of the
            AGENT_STREAM_TOOL_NOTICES environment variable. Defaults to None (env-driven).

    Returns:
        A plain (non-async) `entrypoint(payload)` function suitable for `add_ai_endpoint(s)`:
        it returns a single-shot coroutine when `payload["stream"]` is falsy, or a real
        streaming async generator otherwise.
    """

    def entrypoint(payload: dict[str, Any]) -> Any:
        if payload.get("stream"):
            return _stream(build_agent, payload, _tool_notices_enabled(tool_notices))
        return _run_once(build_agent, payload)

    return entrypoint

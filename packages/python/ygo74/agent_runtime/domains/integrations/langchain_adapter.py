"""Generic LangChain agent adapter.

Wraps any LangChain agent executor (legacy `AgentExecutor` or the newer
`create_agent`/langgraph-based runnables) into an `agent_entrypoint` callable
that is directly pluggable into `add_ai_endpoints`/`add_ai_endpoint`.

This module centralizes technical concerns that are the same for *every*
LangChain-based agent exposed through this runtime, so agent authors only
need to provide business logic (model, tools, system prompt) via a builder
function:

    def build_my_agent() -> Any:
        llm = ChatOpenAI(model=...)
        return create_agent(model=llm, tools=[...], system_prompt=...)

    my_entrypoint = create_langchain_agent_entrypoint(build_my_agent)
    add_ai_endpoints(app, my_entrypoint, default_route_key="my-agent")

Handled here:
- Building the input payload LangChain expects (`{"input": ...}` for the legacy
  `AgentExecutor`, `{"messages": [...]}` for the newer messages-based runnables),
  auto-detected per executor instance.
- Extracting the final answer text from either result shape (single-shot).
- Real token-by-token streaming via `astream_events`, only forwarding actual
  chat model text deltas (`on_chat_model_stream`), so no extra flag is needed
  on the agent author's side to support `stream=true` requests.
- Optional inline tool-call notices (e.g. `> \U0001F527 Calling tool ...`) injected
  directly into the streamed content, so any OpenAI-compatible client (including
  ones with no visibility into server-side tool execution, e.g. LibreChat) can
  show the user that a tool was used. Controlled by AGENT_STREAM_TOOL_NOTICES.
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator, Callable

BuildExecutor = Callable[[], Any] | Any


def _resolve_executor(build_executor: BuildExecutor) -> Any:
    return build_executor() if callable(build_executor) else build_executor


def _is_legacy_agent_executor(executor: Any) -> bool:
    try:
        from langchain.agents import AgentExecutor
    except Exception:
        return False

    return isinstance(executor, AgentExecutor)


def _build_invoke_payload(executor: Any, user_input: str) -> dict[str, Any]:
    if _is_legacy_agent_executor(executor):
        return {"input": user_input}

    return {"messages": [{"role": "user", "content": user_input}]}


def _extract_user_input(payload: dict[str, Any]) -> str:
    incoming = payload.get("input")

    if isinstance(incoming, list):
        return "\n".join(str(item) for item in incoming)

    return str(incoming)


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


def _tool_notices_enabled(override: bool | None) -> bool:
    if override is not None:
        return override

    return os.getenv("AGENT_STREAM_TOOL_NOTICES", "true").strip().lower() not in ("0", "false", "no")


def _format_tool_start_notice(tool_name: str, tool_input: Any) -> str:
    detail = ""
    if isinstance(tool_input, dict):
        query = tool_input.get("query")
        if query:
            detail = f' — "{query}"'

    return f"\n> \U0001F527 _Calling tool `{tool_name}`{detail}..._\n\n"


def _format_tool_end_notice(tool_name: str) -> str:
    return f"\n> \u2705 _Tool `{tool_name}` completed._\n\n"


async def _run_once(build_executor: BuildExecutor, payload: dict[str, Any]) -> dict[str, Any]:
    user_input = _extract_user_input(payload)
    executor = _resolve_executor(build_executor)
    invoke_payload = _build_invoke_payload(executor, user_input)

    result = await executor.ainvoke(invoke_payload)
    output_text = _normalize_agent_output(result)

    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {"role": "assistant", "content": output_text},
        "metadata": {"route_key": payload["route_key"]},
    }


async def _stream(build_executor: BuildExecutor, payload: dict[str, Any], notices_enabled: bool) -> AsyncIterator[str]:
    user_input = _extract_user_input(payload)
    executor = _resolve_executor(build_executor)
    invoke_payload = _build_invoke_payload(executor, user_input)

    async for event in executor.astream_events(invoke_payload, version="v2"):
        event_type = event.get("event")

        if event_type == "on_tool_start":
            if notices_enabled:
                tool_name = str(event.get("name") or "tool")
                tool_input = event.get("data", {}).get("input")
                yield _format_tool_start_notice(tool_name, tool_input)
            continue

        if event_type == "on_tool_end":
            if notices_enabled:
                tool_name = str(event.get("name") or "tool")
                yield _format_tool_end_notice(tool_name)
            continue

        if event_type != "on_chat_model_stream":
            continue

        chunk = event.get("data", {}).get("chunk")
        if chunk is None:
            continue

        delta_text = _extract_chunk_text(chunk)
        if delta_text:
            yield delta_text


def create_langchain_agent_entrypoint(
    build_executor: BuildExecutor,
    *,
    tool_notices: bool | None = None,
) -> Callable[[dict[str, Any]], Any]:
    """Create an `agent_entrypoint` for `add_ai_endpoints` from a LangChain executor.

    Args:
        build_executor: Either a zero-argument factory called once per request
            (recommended default: `build_solution_architect_agent`), or an
            already-built executor instance to reuse across requests.
        tool_notices: Force-enable/disable inline tool-call notices in streamed
            responses. Defaults to the AGENT_STREAM_TOOL_NOTICES env var (true
            unless explicitly set to "false"/"0"/"no").

    Returns:
        A plain (non-async) callable suitable as the `agent_entrypoint` argument
        of `add_ai_endpoints`/`add_ai_endpoint`. It returns a coroutine for
        single-shot (non-streaming) requests, or an async generator of text
        deltas for `stream=true` requests, matching the dual contract expected
        by the FastAPI streaming layer.
    """

    notices_enabled = _tool_notices_enabled(tool_notices)

    def entrypoint(payload: dict[str, Any]) -> Any:
        if payload.get("stream"):
            return _stream(build_executor, payload, notices_enabled)

        return _run_once(build_executor, payload)

    return entrypoint

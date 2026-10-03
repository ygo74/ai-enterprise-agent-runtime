"""Rendering a use-case result in the dialect the caller asked for.

The Standard Exchange envelope is the contract *inside* the runtime. It is not
what an OpenAI or Anthropic client expects to read, and an endpoint published at
``/v1/chat/completions`` is a promise about the wire shape as much as about the
path.

The streaming path already keeps that promise: ``_stream_chunk_frame`` emits
``chat.completion.chunk`` objects with ``choices[0].delta.content``. Before this
module did the same for a single response, the same endpoint answered in two
different dialects depending on ``stream``, and a client able to follow a stream
could not read a plain reply.

Errors are deliberately left in the envelope shape. They already carry an HTTP
status code, which is what a client acts on, and changing how they are rendered
means changing where they are raised - a separate concern from this one.
"""

import json
import time
import uuid
from typing import Any

from ygo74.agent_runtime.domains.endpoints.openai_responses import (
    OpenAIResponsesResult,
    OpenAIResponsesStatus,
)

CHAT_COMPLETIONS = "openai.chat_completions"
RESPONSES = "openai.responses"
ANTHROPIC_MESSAGES = "anthropic.messages"

_ASSISTANT = "assistant"
_STOP = "stop"


def extract_output_text(output: Any) -> str:
    """Reduce a use-case output to the plain text a chat client renders.

    A handler may answer with a string, with a mapping carrying ``content`` or
    ``text``, or with a structured object. The first cases have an obvious
    rendering; anything else is serialised rather than dropped, because silently
    returning an empty message would look like a model failure.
    """

    if isinstance(output, str):
        return output

    if isinstance(output, dict):
        content = output.get("content")
        if isinstance(content, str):
            return content

        text = output.get("text")
        if isinstance(text, str):
            return text

        return json.dumps(output, ensure_ascii=True)

    if output is None:
        return ""

    return str(output)


def map_response(
    endpoint_type: str,
    exchange_response: dict[str, Any],
    *,
    model: Any = None,
    provider_options: dict[str, Any] | None = None,
    request_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render an exchange response for the endpoint that produced it.

    Args:
        endpoint_type: Which dialect the caller is speaking.
        exchange_response: The Standard Exchange response of the use case.
        model: Identifier the caller asked for, echoed back so a client can
            match a reply to the model it selected.
    """

    status = exchange_response.get("status", "error")
    request_id = exchange_response.get("request_id")

    if status != "success":
        if endpoint_type == RESPONSES:
            return _responses_error(exchange_response.get("error"))
        return {
            "request_id": request_id,
            "status": status,
            "endpoint_type": endpoint_type,
            "error": exchange_response.get("error", {"code": "unknown", "message": "unknown error"}),
        }

    output = exchange_response.get("output")

    if endpoint_type == CHAT_COMPLETIONS:
        return _chat_completion(request_id, model, extract_output_text(output))

    if endpoint_type == RESPONSES:
        return _response(
            request_id,
            model,
            output,
            provider_options or {},
            request_metadata or {},
        )

    if endpoint_type == ANTHROPIC_MESSAGES:
        return _anthropic_message(request_id, model, extract_output_text(output))

    # An endpoint type this module does not know about keeps the envelope, so
    # adding a protocol never silently changes the shape of an existing one.
    return {
        "request_id": request_id,
        "status": status,
        "endpoint_type": endpoint_type,
        "output": output,
    }


def _chat_completion(request_id: Any, model: Any, text: str) -> dict[str, Any]:
    """Build an OpenAI ``chat.completion`` object."""
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": _created(),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": _ASSISTANT, "content": text},
                "finish_reason": _STOP,
            }
        ],
    }


def _response(
    request_id: Any,
    model: Any,
    output: Any,
    provider_options: dict[str, Any],
    request_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build an OpenAI Responses object while preserving structured output items."""
    result = OpenAIResponsesResult.from_handler_output(output)
    response = dict(result.fields)
    response.setdefault("id", f"resp_{uuid.uuid4().hex}")
    response["object"] = "response"
    response.setdefault("created_at", _created())
    response.setdefault("model", model)
    status = OpenAIResponsesStatus(str(response.get("status", OpenAIResponsesStatus.COMPLETED.value)))
    response["status"] = status.value
    response["output"] = _complete_output_items(result.output)
    response.setdefault("parallel_tool_calls", provider_options.get("parallel_tool_calls", True))
    response.setdefault("tool_choice", provider_options.get("tool_choice", "auto"))
    response.setdefault("tools", provider_options.get("tools", []))

    for key in _RESPONSE_OPTION_FIELDS:
        if key in provider_options:
            response.setdefault(key, provider_options[key])

    if request_metadata:
        response.setdefault("metadata", request_metadata)

    response["output_text"] = _responses_output_text(response["output"])
    return response


_RESPONSE_OPTION_FIELDS = (
    "access_programs",
    "background",
    "conversation",
    "instructions",
    "max_output_tokens",
    "max_tool_calls",
    "moderation",
    "previous_response_id",
    "prompt",
    "prompt_cache_key",
    "prompt_cache_options",
    "prompt_cache_retention",
    "reasoning",
    "safety_identifier",
    "service_tier",
    "store",
    "temperature",
    "text",
    "top_logprobs",
    "top_p",
    "truncation",
    "user",
)


def _responses_output_text(output_items: list[Any]) -> str:
    parts: list[str] = []
    for item in output_items:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "".join(parts)


def _complete_output_items(output_items: list[Any]) -> list[Any]:
    completed: list[Any] = []
    for item in output_items:
        if not isinstance(item, dict) or item.get("id"):
            completed.append(item)
            continue
        item_copy = dict(item)
        item_copy["id"] = f"msg_{uuid.uuid4().hex}"
        completed.append(item_copy)
    return completed


def _responses_error(error: Any) -> dict[str, Any]:
    error_map = error if isinstance(error, dict) else {}
    category = str(error_map.get("category", "handler_execution"))
    error_type = {
        "validation": "invalid_request_error",
        "authentication": "authentication_error",
        "authorization": "permission_error",
        "routing": "not_found_error",
        "mapping": "invalid_request_error",
        "configuration": "server_error",
        "handler_execution": "server_error",
    }.get(category, "server_error")
    return {
        "error": {
            "message": str(error_map.get("message", "The request failed.")),
            "type": error_type,
            "param": None,
            "code": error_map.get("code"),
        }
    }


def _anthropic_message(request_id: Any, model: Any, text: str) -> dict[str, Any]:
    """Build an Anthropic Messages object."""
    return {
        "id": request_id,
        "type": "message",
        "role": _ASSISTANT,
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
    }


def _created() -> int:
    """Unix timestamp clients use to order replies."""
    return int(time.time())

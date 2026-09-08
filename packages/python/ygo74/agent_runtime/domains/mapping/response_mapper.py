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
from typing import Any

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
        return _response(request_id, model, extract_output_text(output))

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


def _response(request_id: Any, model: Any, text: str) -> dict[str, Any]:
    """Build an OpenAI Responses object.

    ``output_text`` is included alongside ``output`` because it is what most
    clients read first, and computing it here saves every caller from walking
    the content parts.
    """
    return {
        "id": request_id,
        "object": "response",
        "created_at": _created(),
        "model": model,
        "status": "completed",
        "output": [
            {
                "id": request_id,
                "type": "message",
                "role": _ASSISTANT,
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "output_text": text,
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

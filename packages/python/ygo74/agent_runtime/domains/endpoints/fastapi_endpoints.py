from __future__ import annotations

import inspect
import json
import logging
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable, Sequence

try:
    from fastapi import HTTPException, Request
    from fastapi.responses import StreamingResponse

    _FASTAPI_AVAILABLE = True
    _FASTAPI_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - depends on web runtime
    HTTPException = Exception  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    StreamingResponse = None  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False
    _FASTAPI_IMPORT_ERROR = exc

from ygo74.agent_runtime.domains.mapping.request_mapper import map_to_exchange
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response
from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError, AuthorizationError
from ygo74.agent_runtime.domains.auth.authenticator import Authenticator, RequestAuthenticator
from ygo74.agent_runtime.domains.auth.apikey_authenticator import ApiKeyAuthenticator, ApiKeyUserResolver
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtAuthenticator, JwtValidationConfig

AgentEntrypoint = Callable[[dict[str, Any]], Awaitable[Any] | Any]

logger = logging.getLogger(__name__)


def build_request_authenticator(
    *,
    jwt_validation: JwtValidationConfig | None = None,
    api_key_resolver: ApiKeyUserResolver | None = None,
    require_authentication: bool = False,
    authenticators: Sequence[Authenticator] | None = None,
) -> RequestAuthenticator:
    """Assemble the authenticator chain used to authenticate incoming requests.

    JWT is evaluated before API key, so an ``Authorization`` header always wins
    over an ``x-api-key`` header when both are present.
    """

    if authenticators is not None:
        return RequestAuthenticator(list(authenticators), require_authentication=require_authentication)

    chain: list[Authenticator] = [JwtAuthenticator(jwt_validation)]
    if api_key_resolver is not None:
        chain.append(ApiKeyAuthenticator(api_key_resolver))

    return RequestAuthenticator(chain, require_authentication=require_authentication)


def add_ai_endpoints(
    app: Any,
    agent_entrypoint: AgentEntrypoint,
    *,
    default_route_key: str,
    enable_openai_responses: bool = True,
    enable_openai_chat_completions: bool = True,
    enable_anthropic_messages: bool = False,
    jwt_validation: JwtValidationConfig | None = None,
    require_bearer_token: bool = False,
    api_key_resolver: ApiKeyUserResolver | None = None,
    authenticators: Sequence[Authenticator] | None = None,
) -> None:
    """Register AI endpoints on a FastAPI app and forward a uniform payload to agent_entrypoint."""

    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("fastapi is required to use add_ai_endpoints") from _FASTAPI_IMPORT_ERROR

    request_authenticator = build_request_authenticator(
        jwt_validation=jwt_validation,
        api_key_resolver=api_key_resolver,
        require_authentication=require_bearer_token,
        authenticators=authenticators,
    )

    async def _invoke(endpoint_type: str, body: dict[str, Any], request: Request) -> Any:
        payload: dict[str, Any] = {
            "request_id": str((body.get("metadata") or {}).get("request_id") or body.get("request_id") or "unknown"),
            "route_key": str((body.get("metadata") or {}).get("route_key") or body.get("route_key") or default_route_key),
        }
        try:
            payload = _build_raw_payload(
                endpoint_type,
                body,
                request,
                default_route_key,
                request_authenticator=request_authenticator,
            )
            exchange_request = map_to_exchange(endpoint_type, payload)

            uniform_payload = {
                "request_id": exchange_request.request_id,
                "route_key": exchange_request.route_key,
                "endpoint_type": exchange_request.endpoint_type,
                "input": exchange_request.input,
                "stream": exchange_request.stream,
                "metadata": exchange_request.metadata,
                "auth_context": exchange_request.auth_context,
            }

            result = agent_entrypoint(uniform_payload)

            if exchange_request.stream:
                if StreamingResponse is None:  # pragma: no cover - guarded by _FASTAPI_AVAILABLE check above
                    raise RuntimeError("fastapi is required to use streaming responses")

                return StreamingResponse(
                    _stream_response(endpoint_type, exchange_request.request_id, payload.get("model"), result),
                    media_type="text/event-stream",
                )

            if inspect.isawaitable(result):
                result = await result

            exchange_response = _normalize_agent_result(result, exchange_request.request_id, exchange_request.route_key)
            mapped = map_response(endpoint_type, exchange_response)
            status_code = _error_status_code(exchange_response)
            if status_code is not None:
                raise HTTPException(status_code=status_code, detail=mapped)

            return mapped
        except HTTPException:
            # Either raised above from a handler-declared error envelope, or raised
            # directly by developer-owned authorization logic. Preserve it as-is.
            raise
        except AuthorizationError as ex:
            logger.info("Authorization denied for endpoint_type=%s request_id=%s", endpoint_type, payload.get("request_id"))
            err = {
                "request_id": payload["request_id"],
                "status": "error",
                "error": ex.to_dict(),
            }
            raise HTTPException(status_code=403, detail=map_response(endpoint_type, err)) from ex
        except AuthenticationError as ex:
            payload = body.get("metadata") or {}
            logger.warning("Authentication failed for endpoint_type=%s", endpoint_type)
            err = {
                "request_id": str(payload.get("request_id") or body.get("request_id") or "unknown"),
                "status": "error",
                "error": ex.to_dict(),
            }
            raise HTTPException(status_code=401, detail=map_response(endpoint_type, err)) from ex
        except Exception as ex:
            logger.exception(
                "Agent execution failed for endpoint_type=%s request_id=%s route_key=%s",
                endpoint_type,
                payload.get("request_id"),
                payload.get("route_key"),
            )
            err = {
                "request_id": payload["request_id"],
                "status": "error",
                "error": {
                    "code": "agent_execution_error",
                    "category": "handler_execution",
                    "message": str(ex) or repr(ex),
                },
            }
            raise HTTPException(status_code=500, detail=map_response(endpoint_type, err)) from ex

    if enable_openai_responses:

        @app.post("/v1/responses")
        async def openai_responses(body: dict[str, Any], request: Request) -> Any:
            return await _invoke("openai.responses", body, request)

    if enable_openai_chat_completions:

        @app.post("/v1/chat/completions")
        async def openai_chat_completions(body: dict[str, Any], request: Request) -> Any:
            return await _invoke("openai.chat_completions", body, request)

    if enable_anthropic_messages:

        @app.post("/v1/messages")
        async def anthropic_messages(body: dict[str, Any], request: Request) -> Any:
            return await _invoke("anthropic.messages", body, request)


def add_ai_endpoint(
    app: Any,
    agent_entrypoint: AgentEntrypoint,
    *,
    default_route_key: str,
    enable_openai_responses: bool = True,
    enable_openai_chat_completions: bool = True,
    enable_anthropic_messages: bool = False,
    jwt_validation: JwtValidationConfig | None = None,
    require_bearer_token: bool = False,
    api_key_resolver: ApiKeyUserResolver | None = None,
    authenticators: Sequence[Authenticator] | None = None,
) -> None:
    """Alias for add_ai_endpoints with a singular name for API ergonomics."""

    add_ai_endpoints(
        app,
        agent_entrypoint,
        default_route_key=default_route_key,
        enable_openai_responses=enable_openai_responses,
        enable_openai_chat_completions=enable_openai_chat_completions,
        enable_anthropic_messages=enable_anthropic_messages,
        jwt_validation=jwt_validation,
        require_bearer_token=require_bearer_token,
        api_key_resolver=api_key_resolver,
        authenticators=authenticators,
    )


def _build_raw_payload(
    endpoint_type: str,
    body: dict[str, Any],
    request: Any,
    default_route_key: str,
    *,
    request_authenticator: RequestAuthenticator,
) -> dict[str, Any]:
    metadata = dict(body.get("metadata") or {})
    route_key = str(metadata.get("route_key") or body.get("route_key") or default_route_key)
    request_id = str(metadata.get("request_id") or body.get("request_id") or f"req-{uuid.uuid4().hex[:12]}")

    if endpoint_type == "openai.responses":
        normalized_input = body.get("input")
    else:
        normalized_input = body.get("messages", body.get("input"))

    user_context = request_authenticator.authenticate(getattr(request, "headers", None))

    return {
        "request_id": request_id,
        "route_key": route_key,
        "model": body.get("model"),
        "input": normalized_input,
        "metadata": metadata,
        "stream": bool(body.get("stream", False)),
        "auth_context": user_context.to_dict() if user_context is not None else None,
    }


def _error_status_code(exchange_response: dict[str, Any]) -> int | None:
    """Map a handler-declared error envelope to an HTTP status code.

    Developers own authorization decisions, so a handler may return an error
    envelope with category ``authorization`` (or ``authentication``) instead of
    raising. Those must not surface as HTTP 200.
    """

    if exchange_response.get("status") != "error":
        return None

    error = exchange_response.get("error")
    category = error.get("category") if isinstance(error, dict) else None

    return {
        "authorization": 403,
        "authentication": 401,
        "validation": 400,
        "routing": 404,
    }.get(str(category), 500)


def _normalize_agent_result(result: Any, request_id: str, route_key: str) -> dict[str, Any]:
    if isinstance(result, dict):
        if "status" in result:
            normalized = dict(result)
            normalized.setdefault("request_id", request_id)
            normalized.setdefault("metadata", {"route_key": route_key})
            return normalized

        return {
            "request_id": request_id,
            "status": "success",
            "output": result,
            "metadata": {"route_key": route_key},
        }

    status = getattr(result, "status", None)
    if status is not None:
        return {
            "request_id": getattr(result, "request_id", request_id),
            "status": str(status),
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
            "metadata": getattr(result, "metadata", {"route_key": route_key}) or {"route_key": route_key},
        }

    return {
        "request_id": request_id,
        "status": "success",
        "output": result,
        "metadata": {"route_key": route_key},
    }


def _extract_delta_text(chunk: Any) -> str:
    """Extract plain text from a streamed chunk item (string, or dict with delta/content)."""

    if isinstance(chunk, str):
        return chunk

    if isinstance(chunk, dict):
        for key in ("delta", "content", "text"):
            value = chunk.get(key)
            if isinstance(value, str):
                return value

        return json.dumps(chunk, ensure_ascii=True)

    return str(chunk)


def _extract_output_text(output: Any) -> str:
    """Extract plain text from a normalized (non-streaming) agent output."""

    if isinstance(output, str):
        return output

    if isinstance(output, dict):
        content = output.get("content")
        if isinstance(content, str):
            return content

        return json.dumps(output, ensure_ascii=True)

    return str(output)


def _sse_frame(data: dict[str, Any], *, event: str | None = None) -> str:
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=True)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _stream_chunk_frame(endpoint_type: str, request_id: str, model: Any, delta_text: str) -> str:
    if endpoint_type == "openai.chat_completions":
        return _sse_frame(
            {
                "id": request_id,
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"index": 0, "delta": {"content": delta_text}, "finish_reason": None}],
            }
        )

    if endpoint_type == "openai.responses":
        return _sse_frame(
            {
                "type": "response.output_text.delta",
                "response_id": request_id,
                "delta": delta_text,
            }
        )

    if endpoint_type == "anthropic.messages":
        return _sse_frame(
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": delta_text}},
            event="content_block_delta",
        )

    return _sse_frame({"request_id": request_id, "event_type": "chunk", "delta": delta_text})


def _stream_completion_frames(endpoint_type: str, request_id: str, model: Any, full_text: str) -> list[str]:
    if endpoint_type == "openai.chat_completions":
        return [
            _sse_frame(
                {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
            )
        ]

    if endpoint_type == "openai.responses":
        return [
            _sse_frame(
                {
                    "type": "response.completed",
                    "response_id": request_id,
                    "output": {"role": "assistant", "content": full_text},
                }
            )
        ]

    if endpoint_type == "anthropic.messages":
        return [
            _sse_frame({"type": "content_block_stop", "index": 0}, event="content_block_stop"),
            _sse_frame({"type": "message_delta", "delta": {"stop_reason": "end_turn"}}, event="message_delta"),
            _sse_frame({"type": "message_stop"}, event="message_stop"),
        ]

    return [_sse_frame({"request_id": request_id, "event_type": "completion", "final_output": full_text})]


def _stream_start_frames(endpoint_type: str, request_id: str, model: Any) -> list[str]:
    if endpoint_type == "anthropic.messages":
        return [
            _sse_frame(
                {
                    "type": "message_start",
                    "message": {
                        "id": request_id,
                        "type": "message",
                        "role": "assistant",
                        "model": model,
                        "content": [],
                    },
                },
                event="message_start",
            ),
            _sse_frame(
                {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                event="content_block_start",
            ),
        ]

    return []


def _stream_error_frame(endpoint_type: str, request_id: str, message: str) -> str:
    if endpoint_type == "anthropic.messages":
        return _sse_frame({"type": "error", "error": {"type": "api_error", "message": message}}, event="error")

    return _sse_frame(
        {
            "request_id": request_id,
            "status": "error",
            "error": {"code": "agent_execution_error", "category": "handler_execution", "message": message},
        }
    )


async def _stream_response(endpoint_type: str, request_id: str, model: Any, entrypoint_result: Any) -> AsyncIterator[str]:
    """Consume the agent entrypoint result and yield Server-Sent Events for the given endpoint type.

    Supports two entrypoint styles:
    - Real incremental streaming: entrypoint_result is an async generator/iterator of text deltas
      (plain strings, or dicts containing a "delta"/"content"/"text" key).
    - Single-shot: entrypoint_result is a coroutine/plain value resolving to the full output; it is
      emitted as one chunk followed immediately by the completion frames.
    """

    for frame in _stream_start_frames(endpoint_type, request_id, model):
        yield frame

    full_text_parts: list[str] = []

    try:
        if hasattr(entrypoint_result, "__aiter__"):
            async for chunk in entrypoint_result:
                delta_text = _extract_delta_text(chunk)
                full_text_parts.append(delta_text)
                yield _stream_chunk_frame(endpoint_type, request_id, model, delta_text)
        else:
            result = entrypoint_result
            if inspect.isawaitable(result):
                result = await result

            normalized = _normalize_agent_result(result, request_id, "")
            delta_text = _extract_output_text(normalized.get("output"))
            full_text_parts.append(delta_text)
            yield _stream_chunk_frame(endpoint_type, request_id, model, delta_text)
    except AuthorizationError as ex:
        # Response headers are already flushed, so a 403 status is no longer
        # possible: surface the denial as a terminal SSE error frame instead.
        logger.info("Authorization denied mid-stream for endpoint_type=%s request_id=%s", endpoint_type, request_id)
        yield _stream_error_frame(endpoint_type, request_id, ex.message)
        yield _sse_done()
        return
    except Exception as ex:
        logger.exception(
            "Streaming agent execution failed for endpoint_type=%s request_id=%s",
            endpoint_type,
            request_id,
        )
        yield _stream_error_frame(endpoint_type, request_id, str(ex) or repr(ex))
        yield _sse_done()
        return

    full_text = "".join(full_text_parts)
    for frame in _stream_completion_frames(endpoint_type, request_id, model, full_text):
        yield frame

    yield _sse_done()

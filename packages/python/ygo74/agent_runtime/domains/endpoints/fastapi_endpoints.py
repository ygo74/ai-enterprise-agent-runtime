from __future__ import annotations

import inspect
import logging
import uuid
from typing import Any, Awaitable, Callable

try:
    from fastapi import HTTPException, Request

    _FASTAPI_AVAILABLE = True
    _FASTAPI_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - depends on web runtime
    HTTPException = Exception  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False
    _FASTAPI_IMPORT_ERROR = exc

from ygo74.agent_runtime.domains.mapping.request_mapper import map_to_exchange
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response

AgentEntrypoint = Callable[[dict[str, Any]], Awaitable[Any] | Any]

logger = logging.getLogger(__name__)


def add_ai_endpoints(
    app: Any,
    agent_entrypoint: AgentEntrypoint,
    *,
    default_route_key: str,
    enable_openai_responses: bool = True,
    enable_openai_chat_completions: bool = True,
    enable_anthropic_messages: bool = False,
) -> None:
    """Register AI endpoints on a FastAPI app and forward a uniform payload to agent_entrypoint."""

    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("fastapi is required to use add_ai_endpoints") from _FASTAPI_IMPORT_ERROR

    async def _invoke(endpoint_type: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        payload = _build_raw_payload(endpoint_type, body, request, default_route_key)

        try:
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
            if inspect.isawaitable(result):
                result = await result

            exchange_response = _normalize_agent_result(result, exchange_request.request_id, exchange_request.route_key)
            return map_response(endpoint_type, exchange_response)
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
        async def openai_responses(body: dict[str, Any], request: Request) -> dict[str, Any]:
            return await _invoke("openai.responses", body, request)

    if enable_openai_chat_completions:

        @app.post("/v1/chat/completions")
        async def openai_chat_completions(body: dict[str, Any], request: Request) -> dict[str, Any]:
            return await _invoke("openai.chat_completions", body, request)

    if enable_anthropic_messages:

        @app.post("/v1/messages")
        async def anthropic_messages(body: dict[str, Any], request: Request) -> dict[str, Any]:
            return await _invoke("anthropic.messages", body, request)


def add_ai_endpoint(
    app: Any,
    agent_entrypoint: AgentEntrypoint,
    *,
    default_route_key: str,
    enable_openai_responses: bool = True,
    enable_openai_chat_completions: bool = True,
    enable_anthropic_messages: bool = False,
) -> None:
    """Alias for add_ai_endpoints with a singular name for API ergonomics."""

    add_ai_endpoints(
        app,
        agent_entrypoint,
        default_route_key=default_route_key,
        enable_openai_responses=enable_openai_responses,
        enable_openai_chat_completions=enable_openai_chat_completions,
        enable_anthropic_messages=enable_anthropic_messages,
    )


def _build_raw_payload(
    endpoint_type: str,
    body: dict[str, Any],
    request: Any,
    default_route_key: str,
) -> dict[str, Any]:
    metadata = dict(body.get("metadata") or {})
    route_key = str(metadata.get("route_key") or body.get("route_key") or default_route_key)
    request_id = str(metadata.get("request_id") or body.get("request_id") or f"req-{uuid.uuid4().hex[:12]}")

    if endpoint_type == "openai.responses":
        normalized_input = body.get("input")
    else:
        normalized_input = body.get("messages", body.get("input"))

    auth_context = _extract_auth_context(request)

    return {
        "request_id": request_id,
        "route_key": route_key,
        "model": body.get("model"),
        "input": normalized_input,
        "metadata": metadata,
        "stream": bool(body.get("stream", False)),
        "auth_context": auth_context,
    }


def _extract_auth_context(request: Any) -> dict[str, Any] | None:
    headers = getattr(request, "headers", None)
    if headers is None:
        return None

    context: dict[str, Any] = {}
    authorization = headers.get("authorization")
    if authorization:
        context["authorization"] = authorization

    api_key = headers.get("x-api-key")
    if api_key:
        context["x-api-key"] = api_key

    return context or None


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

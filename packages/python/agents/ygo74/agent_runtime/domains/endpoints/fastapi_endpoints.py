from __future__ import annotations

import inspect
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from typing_extensions import deprecated

try:
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse, StreamingResponse

    _FASTAPI_AVAILABLE = True
    _FASTAPI_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001  # pragma: no cover - depends on web runtime
    HTTPException = Exception  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
    StreamingResponse = None  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False
    _FASTAPI_IMPORT_ERROR = exc

from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    ApiKeyAuthenticator,
    ApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_errors import (
    AuthenticationError,
    AuthorizationError,
)
from ygo74.agent_runtime.domains.auth.authenticator import (
    Authenticator,
    RequestAuthenticator,
)
from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    JwtAuthenticator,
    JwtValidationConfig,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    OpenAIResponsesStreamEvent,
)
from ygo74.agent_runtime.domains.discovery.agent_access_policy import AgentAccessPolicy
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.dialect_selector import ProviderDialect
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
    DiscoveryService,
)
from ygo74.agent_runtime.domains.discovery.discovery_errors import (
    DiscoveryError,
    DiscoveryErrorCategory,
    DiscoveryErrorCode,
)
from ygo74.agent_runtime.domains.discovery.model_route_resolver import (
    ModelRouteResolver,
)
from ygo74.agent_runtime.domains.discovery.pagination import PaginationRequest
from ygo74.agent_runtime.domains.endpoints.header_forwarding import (
    DEFAULT_CONVERSATION_HEADER,
    RequestHeaderForwarder,
)
from ygo74.agent_runtime.domains.endpoints.openai_responses import (
    OpenAIResponsesCreateRequest,
    OpenAIResponsesStatus,
)
from ygo74.agent_runtime.domains.mapping.request_mapper import map_to_exchange
from ygo74.agent_runtime.domains.mapping.response_mapper import (
    extract_output_text,
    map_response,
)
from ygo74.agent_runtime.domains.streaming.openai_stream_mapper import (
    OpenAIResponsesStreamEncoder,
)

AgentEntrypoint = Callable[[dict[str, Any]], Awaitable[Any] | Any]
P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger(__name__)


def _with_deprecation_warning(function: Callable[P, R], message: str) -> Callable[P, R]:
    @wraps(function)
    @deprecated(message)
    def deprecated_function(*args: P.args, **kwargs: P.kwargs) -> R:
        return function(*args, **kwargs)

    return deprecated_function


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

    chain: list[Authenticator] = []
    if jwt_validation is not None:
        chain.append(JwtAuthenticator(jwt_validation))

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
    descriptor_registry: DescriptorRegistry | None = None,
    discovery: DiscoveryConfiguration | None = None,
    authorization_policy: AgentAccessPolicy | None = None,
    forwarded_headers: Sequence[str] | None = None,
    conversation_header: str = DEFAULT_CONVERSATION_HEADER,
) -> None:
    """Register AI endpoints on a FastAPI app and forward a uniform payload to agent_entrypoint.

    When both ``descriptor_registry`` and ``authorization_policy`` are supplied,
    the policy is consulted once per invocation (using the descriptor resolved
    for the request's route key) and again for every discovery request, so a
    caller denied at invocation time never sees the agent listed either.

    ``forwarded_headers`` names the request headers a handler may read from
    ``metadata["headers"]``; ``conversation_header`` is additionally promoted to
    ``metadata["conversation_id"]`` so a multi-turn handler finds the
    conversation without knowing the transport. Both are allowlists, and a
    header carrying a credential - including the one the authenticator chain
    reads - is refused here rather than forwarded.
    """

    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("fastapi is required to use add_ai_endpoints") from _FASTAPI_IMPORT_ERROR

    request_authenticator = build_request_authenticator(
        jwt_validation=jwt_validation,
        api_key_resolver=api_key_resolver,
        require_authentication=require_bearer_token,
        authenticators=authenticators,
    )

    header_forwarder = RequestHeaderForwarder.create(
        forwarded=forwarded_headers,
        conversation_header=conversation_header,
        credential_headers=_credential_headers(request_authenticator),
    )

    model_route_resolver = (
        None if descriptor_registry is None else ModelRouteResolver(descriptor_registry)
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
                model_route_resolver=model_route_resolver,
                descriptor_registry=descriptor_registry,
                authorization_policy=authorization_policy,
                header_forwarder=header_forwarder,
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
            if endpoint_type == "openai.responses":
                uniform_payload["provider_options"] = exchange_request.provider_options

            result = agent_entrypoint(uniform_payload)

            if exchange_request.stream:
                if StreamingResponse is None:  # pragma: no cover - guarded by _FASTAPI_AVAILABLE check above
                    raise RuntimeError("fastapi is required to use streaming responses")

                return StreamingResponse(
                    _stream_response(
                        endpoint_type,
                        exchange_request.request_id,
                        payload.get("model"),
                        result,
                        provider_options=payload.get("provider_options"),
                        request_metadata=payload.get("response_metadata"),
                    ),
                    media_type="text/event-stream",
                )

            if inspect.isawaitable(result):
                result = await result

            exchange_response = _normalize_agent_result(result, exchange_request.request_id, exchange_request.route_key)
            mapped = map_response(
                endpoint_type,
                exchange_response,
                model=payload.get("model"),
                provider_options=payload.get("provider_options"),
                request_metadata=payload.get("response_metadata"),
            )
            status_code = _error_status_code(exchange_response)
            if status_code is not None:
                if endpoint_type == "openai.responses" and JSONResponse is not None:
                    return JSONResponse(status_code=status_code, content=mapped)
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
            if endpoint_type == "openai.responses" and JSONResponse is not None:
                return JSONResponse(status_code=403, content=map_response(endpoint_type, err))
            raise HTTPException(status_code=403, detail=map_response(endpoint_type, err)) from ex
        except AuthenticationError as ex:
            payload = body.get("metadata") or {}
            logger.warning("Authentication failed for endpoint_type=%s", endpoint_type)
            err = {
                "request_id": str(payload.get("request_id") or body.get("request_id") or "unknown"),
                "status": "error",
                "error": ex.to_dict(),
            }
            if endpoint_type == "openai.responses" and JSONResponse is not None:
                return JSONResponse(status_code=401, content=map_response(endpoint_type, err))
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
            if endpoint_type == "openai.responses" and JSONResponse is not None:
                return JSONResponse(status_code=500, content=map_response(endpoint_type, err))
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

    if descriptor_registry is not None and discovery is not None:
        discovery_authenticator = RequestAuthenticator(
            list(request_authenticator.authenticators),
            require_authentication=discovery.require_authentication,
        )
        add_discovery_endpoints(
            app,
            descriptor_registry,
            discovery,
            authenticator=discovery_authenticator,
            access_policy=authorization_policy,
        )


_register_ai_endpoints = add_ai_endpoints
add_ai_endpoints = _with_deprecation_warning(
    _register_ai_endpoints,
    "Direct add_ai_endpoints registration is deprecated; use HostingFactory(...).add_agent(...).add_ai_endpoints(...).register().",
)


def add_discovery_endpoints(
    app: Any,
    descriptor_registry: DescriptorRegistry,
    discovery: DiscoveryConfiguration,
    *,
    authenticator: RequestAuthenticator | None = None,
    access_policy: AgentAccessPolicy | None = None,
) -> None:
    """Register the model discovery routes.

    The shared ``/v1/models`` path serves whichever dialect the request selects.
    The per-dialect paths are registered only when both surfaces are enabled, so a
    host that exposes a single provider does not advertise the other one.

    ``authenticator`` identifies the caller (best-effort unless
    ``discovery.require_authentication`` is set) so ``access_policy`` can filter
    listings and single-model retrieval the same way it gates invocation.
    """

    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("fastapi is required to use add_discovery_endpoints") from _FASTAPI_IMPORT_ERROR

    if not discovery.any_model_surface_enabled:
        return

    service = DiscoveryService(descriptor_registry, discovery, access_policy=access_policy)
    prefix = discovery.route_prefix.rstrip("/")

    def _authenticate(request: Request) -> Any:
        if authenticator is None:
            return None
        return authenticator.authenticate(getattr(request, "headers", None))

    def _list(request: Request, dialect: ProviderDialect | None) -> Any:
        try:
            auth_context = _authenticate(request)
            return service.list_models(
                headers=getattr(request, "headers", None),
                dialect=dialect,
                pagination=_pagination_from_query(request),
                auth_context=auth_context,
            )
        except AuthenticationError as ex:
            raise _discovery_auth_error(ex) from ex
        except DiscoveryError as ex:
            raise _discovery_http_error(ex) from ex

    def _get(request: Request, model_id: str, dialect: ProviderDialect | None) -> Any:
        try:
            auth_context = _authenticate(request)
            return service.get_model(
                model_id,
                headers=getattr(request, "headers", None),
                dialect=dialect,
                auth_context=auth_context,
            )
        except AuthenticationError as ex:
            raise _discovery_auth_error(ex) from ex
        except DiscoveryError as ex:
            raise _discovery_http_error(ex) from ex

    @app.get(f"{prefix}/v1/models")
    async def list_models(request: Request) -> Any:
        return _list(request, None)

    @app.get(f"{prefix}/v1/models/{{model_id}}")
    async def get_model(model_id: str, request: Request) -> Any:
        return _get(request, model_id, None)

    if discovery.enable_openai_models and discovery.enable_anthropic_models:

        @app.get(f"{prefix}/openai/v1/models")
        async def list_openai_models(request: Request) -> Any:
            return _list(request, ProviderDialect.OPENAI)

        @app.get(f"{prefix}/openai/v1/models/{{model_id}}")
        async def get_openai_model(model_id: str, request: Request) -> Any:
            return _get(request, model_id, ProviderDialect.OPENAI)

        @app.get(f"{prefix}/anthropic/v1/models")
        async def list_anthropic_models(request: Request) -> Any:
            return _list(request, ProviderDialect.ANTHROPIC)

        @app.get(f"{prefix}/anthropic/v1/models/{{model_id}}")
        async def get_anthropic_model(model_id: str, request: Request) -> Any:
            return _get(request, model_id, ProviderDialect.ANTHROPIC)


_DISCOVERY_STATUS_BY_CATEGORY: dict[str, int] = {
    str(DiscoveryErrorCategory.NOT_FOUND): 404,
    str(DiscoveryErrorCategory.VALIDATION): 400,
    str(DiscoveryErrorCategory.CONFIGURATION): 500,
}


def _discovery_http_error(error: DiscoveryError) -> Any:
    status_code = _DISCOVERY_STATUS_BY_CATEGORY.get(str(error.category), 500)
    logger.info("Discovery request failed code=%s category=%s", error.code, error.category)
    return HTTPException(status_code=status_code, detail={"error": error.to_dict()})


def _discovery_auth_error(error: AuthenticationError) -> Any:
    logger.warning("Discovery request authentication failed code=%s", error.code)
    return HTTPException(status_code=401, detail={"error": error.to_dict()})


def _pagination_from_query(request: Any) -> PaginationRequest:
    params = getattr(request, "query_params", None)
    getter = getattr(params, "get", None)
    if not callable(getter):
        return PaginationRequest()

    raw_limit = getter("limit")
    limit: int | None = None
    if isinstance(raw_limit, str) and raw_limit.strip():
        try:
            limit = int(raw_limit)
        except ValueError as exc:
            raise DiscoveryError(
                code=DiscoveryErrorCode.INVALID_PAGINATION,
                message="limit must be an integer",
            ) from exc

    return PaginationRequest(
        limit=limit,
        after_id=_optional_query(getter("after_id")),
        before_id=_optional_query(getter("before_id")),
    )


def _optional_query(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


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
    descriptor_registry: DescriptorRegistry | None = None,
    discovery: DiscoveryConfiguration | None = None,
    authorization_policy: AgentAccessPolicy | None = None,
    forwarded_headers: Sequence[str] | None = None,
    conversation_header: str = DEFAULT_CONVERSATION_HEADER,
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
        descriptor_registry=descriptor_registry,
        discovery=discovery,
        authorization_policy=authorization_policy,
        forwarded_headers=forwarded_headers,
        conversation_header=conversation_header,
    )


def _credential_headers(authenticator: RequestAuthenticator) -> tuple[str, ...]:
    """Return the headers the authenticator chain reads a credential from.

    Collected from the chain rather than hard-coded, so renaming an API key
    header keeps it out of a handler's reach instead of silently making it
    forwardable.
    """

    names: list[str] = []
    for scheme in authenticator.authenticators:
        name = getattr(scheme, "header_name", None) or getattr(scheme, "HEADER_NAME", None)
        if isinstance(name, str) and name.strip():
            names.append(name)

    return tuple(names)


def _build_raw_payload(
    endpoint_type: str,
    body: dict[str, Any],
    request: Any,
    default_route_key: str,
    *,
    request_authenticator: RequestAuthenticator,
    model_route_resolver: ModelRouteResolver | None = None,
    descriptor_registry: DescriptorRegistry | None = None,
    authorization_policy: AgentAccessPolicy | None = None,
    header_forwarder: RequestHeaderForwarder | None = None,
) -> dict[str, Any]:
    forwarder = header_forwarder or RequestHeaderForwarder.create()
    metadata = forwarder.apply(body.get("metadata") or {}, getattr(request, "headers", None))
    route_key = str(
        metadata.get("route_key")
        or body.get("route_key")
        # An identifier advertised by discovery is accepted verbatim as `model`, so
        # clients can round-trip a listing entry without knowing the internal route
        # key. An explicit route key still wins, and an unknown model falls back to
        # the default rather than being routed somewhere unintended.
        or (model_route_resolver.route_key_for(body.get("model")) if model_route_resolver else None)
        or default_route_key
    )
    request_id = str(metadata.get("request_id") or body.get("request_id") or f"req-{uuid.uuid4().hex[:12]}")

    if endpoint_type == "openai.responses":
        responses_request = OpenAIResponsesCreateRequest.from_payload(body)
        normalized_input = responses_request.input
    else:
        normalized_input = body.get("messages", body.get("input"))

    user_context = request_authenticator.authenticate(getattr(request, "headers", None))

    # The same policy that filters discovery listings gates invocation here, so
    # a caller never invokes an agent it would not have seen listed. A raising
    # policy fails closed: the agent is treated as denied rather than letting
    # the exception surface as an unrelated 500.
    if authorization_policy is not None and descriptor_registry is not None:
        target_descriptor = descriptor_registry.find_by_route_key(route_key)
        if target_descriptor is not None:
            try:
                authorized = authorization_policy.is_authorized(target_descriptor, user_context)
            except Exception:
                logger.warning(
                    "Authorization policy raised for agent_id=%s; treating as denied",
                    target_descriptor.agent_id,
                    exc_info=True,
                )
                authorized = False
            if not authorized:
                raise AuthorizationError(
                    code="agent_access_denied",
                    message=f"Access to agent '{target_descriptor.agent_id}' is denied",
                    details={"agentId": target_descriptor.agent_id},
                )

    return {
        "request_id": request_id,
        "route_key": route_key,
        "model": body.get("model"),
        "input": normalized_input,
        "metadata": metadata,
        "stream": bool(body.get("stream", False)),
        "auth_context": user_context.to_dict() if user_context is not None else None,
        "provider_options": responses_request.provider_options if endpoint_type == "openai.responses" else None,
        "response_metadata": dict(body.get("metadata") or {}) if endpoint_type == "openai.responses" else None,
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
    """Extract plain text from a normalized (non-streaming) agent output.

    Delegates to the mapping domain so a streamed chunk and a single response
    reduce an output to text the same way.
    """

    return extract_output_text(output)


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


async def _stream_response(
    endpoint_type: str,
    request_id: str,
    model: Any,
    entrypoint_result: Any,
    *,
    provider_options: dict[str, Any] | None = None,
    request_metadata: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Consume the agent entrypoint result and yield Server-Sent Events for the given endpoint type.

    Supports two entrypoint styles:
    - Real incremental streaming: entrypoint_result is an async generator/iterator of text deltas
      (plain strings, or dicts containing a "delta"/"content"/"text" key).
    - Single-shot: entrypoint_result is a coroutine/plain value resolving to the full output; it is
      emitted as one chunk followed immediately by the completion frames.
    """

    if endpoint_type == "openai.responses":
        async for frame in _stream_openai_responses(
            request_id,
            model,
            entrypoint_result,
            provider_options=provider_options or {},
            request_metadata=request_metadata or {},
        ):
            yield frame
        return

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


async def _stream_openai_responses(
    request_id: str,
    model: Any,
    entrypoint_result: Any,
    *,
    provider_options: dict[str, Any],
    request_metadata: dict[str, Any],
) -> AsyncIterator[str]:
    """Stream either plain text deltas or typed, complete Responses events."""
    encoder = OpenAIResponsesStreamEncoder()
    response_id = f"resp_{uuid.uuid4().hex}"
    created_at = int(time.time())
    try:
        resolved_result = entrypoint_result
        if inspect.isawaitable(resolved_result):
            resolved_result = await resolved_result
    except Exception as ex:  # noqa: BLE001
        failed_response = _responses_wire_response(
            request_id,
            model,
            response_id,
            created_at,
            status=OpenAIResponsesStatus.FAILED,
            output=[],
            provider_options=provider_options,
            request_metadata=request_metadata,
            error={"code": "server_error", "message": str(ex) or repr(ex), "type": "server_error"},
        )
        yield _encode_responses_event(
            encoder,
            "response.failed",
            {"response": failed_response},
            0,
        )
        return

    iterator = resolved_result.__aiter__() if hasattr(resolved_result, "__aiter__") else None
    first: Any = None
    has_first = False

    if iterator is not None:
        try:
            first = await anext(iterator)
            has_first = True
        except StopAsyncIteration:
            pass

    try:
        first_event = _try_responses_event(first, encoder) if has_first else None
    except ValueError as ex:
        failed_response = _responses_wire_response(
            request_id,
            model,
            response_id,
            created_at,
            status=OpenAIResponsesStatus.FAILED,
            output=[],
            provider_options=provider_options,
            request_metadata=request_metadata,
            error={"code": "invalid_event", "message": str(ex), "type": "server_error"},
        )
        yield _encode_responses_event(
            encoder,
            "response.failed",
            {"response": failed_response},
            0,
        )
        return
    if first_event is not None:
        async for frame in _forward_responses_events(
            iterator,
            first_event,
            encoder,
            request_id=request_id,
            model=model,
            response_id=response_id,
            created_at=created_at,
            provider_options=provider_options,
            request_metadata=request_metadata,
        ):
            yield frame
        return

    response = _responses_wire_response(
        request_id,
        model,
        response_id,
        created_at,
        status=OpenAIResponsesStatus.IN_PROGRESS,
        output=[],
        provider_options=provider_options,
        request_metadata=request_metadata,
    )
    sequence = 0
    for event_type in ("response.created", "response.in_progress"):
        yield _encode_responses_event(encoder, event_type, {"response": response}, sequence)
        sequence += 1

    item_id = f"msg_{uuid.uuid4().hex}"
    content_part = {"type": "output_text", "text": "", "annotations": []}
    message = {
        "id": item_id,
        "type": "message",
        "role": "assistant",
        "status": "in_progress",
        "content": [],
    }
    yield _encode_responses_event(
        encoder,
        "response.output_item.added",
        {"output_index": 0, "item": message},
        sequence,
    )
    sequence += 1
    yield _encode_responses_event(
        encoder,
        "response.content_part.added",
        {"output_index": 0, "content_index": 0, "item_id": item_id, "part": content_part},
        sequence,
    )
    sequence += 1

    full_text_parts: list[str] = []
    try:
        if iterator is not None:
            if has_first:
                delta_text = _extract_delta_text(first)
                full_text_parts.append(delta_text)
                yield _encode_responses_text_delta(encoder, delta_text, item_id, sequence)
                sequence += 1
            async for chunk in iterator:
                delta_text = _extract_delta_text(chunk)
                full_text_parts.append(delta_text)
                yield _encode_responses_text_delta(encoder, delta_text, item_id, sequence)
                sequence += 1
        else:
            normalized = _normalize_agent_result(resolved_result, request_id, "")
            delta_text = _extract_output_text(normalized.get("output"))
            full_text_parts.append(delta_text)
            yield _encode_responses_text_delta(encoder, delta_text, item_id, sequence)
            sequence += 1
    except Exception as ex:
        logger.exception("Responses streaming failed for request_id=%s", request_id)
        failed_response = _responses_wire_response(
            request_id,
            model,
            response_id,
            created_at,
            status=OpenAIResponsesStatus.FAILED,
            output=[],
            provider_options=provider_options,
            request_metadata=request_metadata,
            error={"code": "server_error", "message": str(ex) or repr(ex), "type": "server_error"},
        )
        yield _encode_responses_event(
            encoder,
            "response.failed",
            {"response": failed_response},
            sequence,
        )
        return

    full_text = "".join(full_text_parts)
    content_part = {"type": "output_text", "text": full_text, "annotations": []}
    message = {**message, "status": "completed", "content": [content_part]}
    yield _encode_responses_event(
        encoder,
        "response.output_text.done",
        {"content_index": 0, "item_id": item_id, "output_index": 0, "text": full_text, "logprobs": []},
        sequence,
    )
    sequence += 1
    yield _encode_responses_event(
        encoder,
        "response.content_part.done",
        {"output_index": 0, "content_index": 0, "item_id": item_id, "part": content_part},
        sequence,
    )
    sequence += 1
    yield _encode_responses_event(
        encoder,
        "response.output_item.done",
        {"output_index": 0, "item": message},
        sequence,
    )
    sequence += 1
    completed_response = _responses_wire_response(
        request_id,
        model,
        response_id,
        created_at,
        status=OpenAIResponsesStatus.COMPLETED,
        output=[message],
        provider_options=provider_options,
        request_metadata=request_metadata,
    )
    yield _encode_responses_event(
        encoder,
        "response.completed",
        {"response": completed_response},
        sequence,
    )


def _try_responses_event(value: Any, encoder: OpenAIResponsesStreamEncoder) -> OpenAIResponsesStreamEvent | None:
    if isinstance(value, OpenAIResponsesStreamEvent):
        return value
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        return None
    event_type = value["type"]
    if event_type != "error" and not event_type.startswith("response."):
        return None
    return encoder.create_event(value)


async def _forward_responses_events(
    iterator: Any,
    first_event: OpenAIResponsesStreamEvent,
    encoder: OpenAIResponsesStreamEncoder,
    *,
    request_id: str,
    model: Any,
    response_id: str,
    created_at: int,
    provider_options: dict[str, Any],
    request_metadata: dict[str, Any],
) -> AsyncIterator[str]:
    sequence = 0
    event = first_event
    error_message: str | None = None
    try:
        while True:
            payload = dict(event.payload)
            payload.setdefault("sequence_number", sequence)
            event = OpenAIResponsesStreamEvent(event.event_type, payload)
            yield encoder.encode(event)
            sequence += 1
            if event.event_type.value in {
                "response.completed",
                "response.failed",
                "response.incomplete",
                "error",
            }:
                return
            next_value = await anext(iterator)
            next_event = _try_responses_event(next_value, encoder)
            if next_event is None:
                error_message = "A Responses event stream cannot switch to plain text after its first event."
                break
            event = next_event
    except StopAsyncIteration:
        pass
    except Exception as ex:
        logger.exception("Responses event stream failed for request_id=%s", request_id)
        error_message = str(ex) or repr(ex)

    failed_response = _responses_wire_response(
        request_id,
        model,
        response_id,
        created_at,
        status=OpenAIResponsesStatus.FAILED,
        output=[],
        provider_options=provider_options,
        request_metadata=request_metadata,
        error={
            "code": "server_error",
            "message": error_message or "The event stream ended without a terminal event.",
            "type": "server_error",
        },
    )
    yield _encode_responses_event(
        encoder,
        "response.failed",
        {"response": failed_response},
        sequence,
    )


def _responses_wire_response(
    request_id: str,
    model: Any,
    response_id: str,
    created_at: int,
    *,
    status: OpenAIResponsesStatus,
    output: list[dict[str, Any]],
    provider_options: dict[str, Any],
    request_metadata: dict[str, Any],
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response_output: dict[str, Any] = {
        "id": response_id,
        "created_at": created_at,
        "status": status.value,
        "output": output,
    }
    if error is not None:
        response_output["error"] = error
    return map_response(
        "openai.responses",
        {"request_id": request_id, "status": "success", "output": response_output},
        model=model,
        provider_options=provider_options,
        request_metadata=request_metadata,
    )


def _encode_responses_event(
    encoder: OpenAIResponsesStreamEncoder,
    event_type: str,
    payload: dict[str, Any],
    sequence: int,
) -> str:
    full_payload = {"type": event_type, "sequence_number": sequence, **payload}
    return encoder.encode(encoder.create_event(full_payload))


def _encode_responses_text_delta(
    encoder: OpenAIResponsesStreamEncoder,
    delta: str,
    item_id: str,
    sequence: int,
) -> str:
    return _encode_responses_event(
        encoder,
        "response.output_text.delta",
        {
            "content_index": 0,
            "delta": delta,
            "item_id": item_id,
            "output_index": 0,
            "logprobs": [],
        },
        sequence,
    )

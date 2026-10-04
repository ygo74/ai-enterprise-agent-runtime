from __future__ import annotations

import inspect
import logging
import uuid
from collections.abc import Callable, Sequence
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
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    Termination,
    TerminationStatus,
)
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
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
)
from ygo74.agent_runtime.domains.mapping.output_normalizer import OutputNormalizer
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProjectionError,
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mapping.request_mapper import map_to_exchange
from ygo74.agent_runtime.domains.mapping.response_mapper import (
    ResponseMapper,
    map_response,
)
from ygo74.agent_runtime.domains.streaming.stream_processor import (
    AgentInvocation,
    StreamProcessor,
)

AgentEntrypoint = Callable[[dict[str, Any]], AgentInvocation]
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
        return RequestAuthenticator(
            list(authenticators), require_authentication=require_authentication
        )

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
        raise RuntimeError(
            "fastapi is required to use add_ai_endpoints"
        ) from _FASTAPI_IMPORT_ERROR

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

    async def _invoke(
        endpoint_type: str, body: dict[str, Any], request: Request
    ) -> Any:
        payload: dict[str, Any] = {
            "request_id": str(
                (body.get("metadata") or {}).get("request_id")
                or body.get("request_id")
                or "unknown"
            ),
            "route_key": str(
                (body.get("metadata") or {}).get("route_key")
                or body.get("route_key")
                or default_route_key
            ),
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
            context = ProjectionContext(
                OutputProtocol(endpoint_type),
                exchange_request.request_id,
                exchange_request.route_key,
                payload.get("model"),
                payload.get("provider_options") or {},
                payload.get("response_metadata") or {},
            )

            if exchange_request.stream:
                if (
                    StreamingResponse is None
                ):  # pragma: no cover - guarded by _FASTAPI_AVAILABLE check above
                    raise RuntimeError("fastapi is required to use streaming responses")

                return StreamingResponse(
                    StreamProcessor().stream(result, context),
                    media_type="text/event-stream",
                )

            if inspect.isawaitable(result):
                result = await result

            exchange_response = OutputNormalizer().normalize(
                result, request_id=exchange_request.request_id
            )
            mapped = ResponseMapper().project(exchange_response, context)
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
            logger.info(
                "Authorization denied for endpoint_type=%s request_id=%s",
                endpoint_type,
                payload.get("request_id"),
            )
            err = AgentOutput(
                termination=Termination(
                    TerminationStatus.FAILED,
                    error=ErrorEnvelope(ex.code, str(ex.category), ex.message),
                )
            )
            if endpoint_type == "openai.responses" and JSONResponse is not None:
                return JSONResponse(
                    status_code=403,
                    content=map_response(
                        endpoint_type, err, request_id=payload["request_id"]
                    ),
                )
            raise HTTPException(
                status_code=403,
                detail=map_response(
                    endpoint_type, err, request_id=payload["request_id"]
                ),
            ) from ex
        except AuthenticationError as ex:
            payload = body.get("metadata") or {}
            logger.warning("Authentication failed for endpoint_type=%s", endpoint_type)
            err = AgentOutput(
                termination=Termination(
                    TerminationStatus.FAILED,
                    error=ErrorEnvelope(ex.code, str(ex.category), ex.message),
                )
            )
            if endpoint_type == "openai.responses" and JSONResponse is not None:
                return JSONResponse(
                    status_code=401,
                    content=map_response(
                        endpoint_type,
                        err,
                        request_id=str(payload.get("request_id") or "unknown"),
                    ),
                )
            raise HTTPException(
                status_code=401,
                detail=map_response(
                    endpoint_type,
                    err,
                    request_id=str(payload.get("request_id") or "unknown"),
                ),
            ) from ex
        except Exception as ex:
            logger.warning(
                "Agent execution failed for endpoint_type=%s request_id=%s route_key=%s",
                endpoint_type,
                payload.get("request_id"),
                payload.get("route_key"),
            )
            err = AgentOutput(
                termination=Termination(
                    TerminationStatus.FAILED,
                    error=ErrorEnvelope(
                        getattr(ex, "code", "agent_execution_error"),
                        ex.category
                        if isinstance(ex, OutputProjectionError)
                        else "handler_execution",
                        str(ex)
                        if isinstance(ex, OutputProjectionError)
                        else "Agent output is invalid"
                        if isinstance(ex, ValueError)
                        else "Agent execution failed",
                    ),
                )
            )
            if endpoint_type == "openai.responses" and JSONResponse is not None:
                return JSONResponse(
                    status_code=500,
                    content=map_response(
                        endpoint_type, err, request_id=payload["request_id"]
                    ),
                )
            raise HTTPException(
                status_code=500,
                detail=map_response(
                    endpoint_type, err, request_id=payload["request_id"]
                ),
            ) from ex

    if enable_openai_responses:

        @app.post("/v1/responses")
        async def openai_responses(body: dict[str, Any], request: Request) -> Any:
            return await _invoke("openai.responses", body, request)

    if enable_openai_chat_completions:

        @app.post("/v1/chat/completions")
        async def openai_chat_completions(
            body: dict[str, Any], request: Request
        ) -> Any:
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
        raise RuntimeError(
            "fastapi is required to use add_discovery_endpoints"
        ) from _FASTAPI_IMPORT_ERROR

    if not discovery.any_model_surface_enabled:
        return

    service = DiscoveryService(
        descriptor_registry, discovery, access_policy=access_policy
    )
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
    logger.info(
        "Discovery request failed code=%s category=%s", error.code, error.category
    )
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
        name = getattr(scheme, "header_name", None) or getattr(
            scheme, "HEADER_NAME", None
        )
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
    metadata = forwarder.apply(
        body.get("metadata") or {}, getattr(request, "headers", None)
    )
    route_key = str(
        metadata.get("route_key")
        or body.get("route_key")
        # An identifier advertised by discovery is accepted verbatim as `model`, so
        # clients can round-trip a listing entry without knowing the internal route
        # key. An explicit route key still wins, and an unknown model falls back to
        # the default rather than being routed somewhere unintended.
        or (
            model_route_resolver.route_key_for(body.get("model"))
            if model_route_resolver
            else None
        )
        or default_route_key
    )
    request_id = str(
        metadata.get("request_id")
        or body.get("request_id")
        or f"req-{uuid.uuid4().hex[:12]}"
    )

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
                authorized = authorization_policy.is_authorized(
                    target_descriptor, user_context
                )
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
        "provider_options": responses_request.provider_options
        if endpoint_type == "openai.responses"
        else None,
        "response_metadata": dict(body.get("metadata") or {})
        if endpoint_type == "openai.responses"
        else None,
    }


def _error_status_code(output: AgentOutput) -> int | None:
    error = output.termination.error
    if output.termination.status != TerminationStatus.FAILED or error is None:
        return None
    return {
        "authorization": 403,
        "authentication": 401,
        "validation": 400,
        "routing": 404,
    }.get(error.category, 500)

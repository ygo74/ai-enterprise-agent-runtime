from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from discovery_fixtures import make_descriptor
from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    ApiKeyAuthenticator,
    ApiKeyUserResolver,
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.auth.authenticator import Authenticator
from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    DiscoveredJwksKeyResolver,
    JwksKeyResolver,
    JwtAuthenticator,
    JwtKeyResolver,
    RotatingKeyResolver,
    StaticPublicKeyResolver,
    StaticSymmetricKeyResolver,
)
from ygo74.agent_runtime.domains.discovery.agent_access_policy import (
    AgentAccessPolicy,
    RoleRequiredAccessPolicy,
)
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.endpoints.hosting_factory import (
    EndpointSurface,
    HostingConfigurationError,
    HostingFactory,
)
from ygo74.agent_runtime.domains.humanapproval.confirmation import (
    ConfiguredConfirmationPolicy,
    ConfirmationAuthority,
    ConfirmationPolicy,
    ConfirmationPreferenceStore,
    InMemoryConfirmationPreferenceStore,
)
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    InMemoryPendingConfirmationStore,
    PendingConfirmationStore,
)
from ygo74.agent_runtime.domains.humanapproval.unattended import (
    UnattendedApprovalAuthority,
)
from ygo74.agent_runtime.domains.security.audit import (
    AuditTrail,
    InMemoryAuditTrail,
    LoggingAuditTrail,
)
from ygo74.agent_runtime.routing.dispatcher import Dispatcher
from ygo74.agent_runtime.routing.dispatcher_impl import DispatcherImpl

_SURFACE_REQUESTS: tuple[tuple[EndpointSurface, str, dict[str, Any]], ...] = (
    (
        EndpointSurface.OPENAI_RESPONSES,
        "/v1/responses",
        {"model": "demo-agent", "input": "hello"},
    ),
    (
        EndpointSurface.OPENAI_CHAT_COMPLETIONS,
        "/v1/chat/completions",
        {"model": "demo-agent", "messages": [{"role": "user", "content": "hello"}]},
    ),
    (
        EndpointSurface.ANTHROPIC_MESSAGES,
        "/v1/messages",
        {"model": "demo-agent", "max_tokens": 32, "messages": [{"role": "user", "content": "hello"}]},
    ),
)


async def _entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {
            "content": f"{payload['endpoint_type']}:{payload['route_key']}",
            "auth_context": payload["auth_context"],
        },
    }


def _configured_factory(
    app: FastAPI,
    surfaces: tuple[EndpointSurface, ...],
    *,
    authentication: AuthenticationPolicy | None = None,
    discovery: DiscoveryConfiguration | None = None,
) -> HostingFactory:
    factory = (
        HostingFactory(app)
        .add_agent(_entrypoint, make_descriptor("demo-agent"))
        .add_ai_endpoints(*surfaces)
        .add_security(authentication or AuthenticationPolicy.anonymous())
    )
    if discovery is not None:
        factory.add_discovery(discovery)
    return factory


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=json, headers=headers)


@pytest.mark.parametrize(("surface", "path", "body"), _SURFACE_REQUESTS)
def test_factory_registers_each_supported_invocation_surface(
    surface: EndpointSurface, path: str, body: dict[str, Any]
) -> None:
    app = FastAPI()
    _configured_factory(app, (surface,)).register()

    response = asyncio.run(_request(app, "POST", path, json=body))

    assert response.status_code == 200
    assert response.json()


def test_factory_registers_only_selected_surfaces_and_routes_by_descriptor() -> None:
    app = FastAPI()
    seen: list[dict[str, Any]] = []

    async def entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(payload)
        return await _entrypoint(payload)

    factory = (
        HostingFactory(app)
        .add_agent(entrypoint, make_descriptor("demo-agent"))
        .add_ai_endpoints(EndpointSurface.OPENAI_RESPONSES, EndpointSurface.ANTHROPIC_MESSAGES)
        .add_security(AuthenticationPolicy.anonymous())
    )
    factory.register()

    responses = asyncio.run(_request(app, "POST", "/v1/responses", json=_SURFACE_REQUESTS[0][2]))
    disabled_chat = asyncio.run(_request(app, "POST", "/v1/chat/completions", json=_SURFACE_REQUESTS[1][2]))
    messages = asyncio.run(_request(app, "POST", "/v1/messages", json=_SURFACE_REQUESTS[2][2]))

    assert responses.status_code == 200
    assert "openai.responses:route-demo-agent" in responses.json()["output_text"]
    assert disabled_chat.status_code == 404
    assert messages.status_code == 200
    assert [payload["route_key"] for payload in seen] == ["route-demo-agent", "route-demo-agent"]


def test_factory_matches_direct_registration_for_routes_and_responses() -> None:
    descriptor = make_descriptor("demo-agent")
    discovery = DiscoveryConfiguration(enable_openai_models=True)
    authentication = AuthenticationPolicy.anonymous()
    factory_app = FastAPI()
    direct_app = FastAPI()

    (
        HostingFactory(factory_app)
        .add_agent(_entrypoint, descriptor)
        .add_ai_endpoints(EndpointSurface.OPENAI_RESPONSES, EndpointSurface.ANTHROPIC_MESSAGES)
        .add_security(authentication)
        .add_discovery(discovery)
        .register()
    )
    add_ai_endpoints(
        direct_app,
        _entrypoint,
        default_route_key=descriptor.route_key,
        enable_openai_responses=True,
        enable_openai_chat_completions=False,
        enable_anthropic_messages=True,
        require_bearer_token=authentication.requires_authentication,
        authenticators=authentication.authenticators,
        descriptor_registry=DescriptorRegistry((descriptor,)),
        discovery=discovery,
    )

    factory_routes = {(route.path, tuple(sorted(route.methods or ()))) for route in factory_app.routes}
    direct_routes = {(route.path, tuple(sorted(route.methods or ()))) for route in direct_app.routes}
    assert factory_routes == direct_routes

    response_body = _SURFACE_REQUESTS[0][2]
    factory_response = asyncio.run(_request(factory_app, "POST", "/v1/responses", json=response_body))
    direct_response = asyncio.run(_request(direct_app, "POST", "/v1/responses", json=response_body))
    assert factory_response.status_code == direct_response.status_code == 200
    assert factory_response.json()["output_text"] == direct_response.json()["output_text"]

    factory_models = asyncio.run(_request(factory_app, "GET", "/v1/models"))
    direct_models = asyncio.run(_request(direct_app, "GET", "/v1/models"))
    assert factory_models.status_code == direct_models.status_code == 200
    assert factory_models.json() == direct_models.json()


def test_factory_preserves_streaming_response_behavior() -> None:
    app = FastAPI()

    def streaming_entrypoint(payload: dict[str, Any]) -> Any:
        del payload

        async def chunks() -> AsyncIterator[str]:
            yield "hello"

        return chunks()

    (
        HostingFactory(app)
        .add_agent(streaming_entrypoint, make_descriptor("demo-agent", streaming=True))
        .add_ai_endpoints(EndpointSurface.OPENAI_CHAT_COMPLETIONS)
        .add_security(AuthenticationPolicy.anonymous())
        .register()
    )

    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/chat/completions",
            json={"model": "demo-agent", "messages": [{"role": "user", "content": "hello"}], "stream": True},
        )
    )

    assert response.status_code == 200
    assert "chat.completion.chunk" in response.text
    assert "hello" in response.text
    assert "data: [DONE]" in response.text


def test_discovery_is_opt_in_and_uses_its_own_authentication_requirement() -> None:
    resolver = StaticApiKeyUserResolver({"key-1": ResolvedUser(user_id="service-1")})
    authentication = AuthenticationPolicy.api_key(resolver)

    protected_app = FastAPI()
    _configured_factory(
        protected_app,
        (EndpointSurface.OPENAI_RESPONSES,),
        authentication=authentication,
        discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=True),
    ).register()

    unprotected_app = FastAPI()
    _configured_factory(
        unprotected_app,
        (EndpointSurface.OPENAI_RESPONSES,),
        authentication=authentication,
        discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=False),
    ).register()

    protected_without_key = asyncio.run(_request(protected_app, "GET", "/v1/models"))
    protected_with_key = asyncio.run(
        _request(protected_app, "GET", "/v1/models", headers={"x-api-key": "key-1"})
    )
    unprotected_without_key = asyncio.run(_request(unprotected_app, "GET", "/v1/models"))

    assert protected_without_key.status_code == 401
    assert protected_with_key.status_code == 200
    assert unprotected_without_key.status_code == 200


def test_invocation_authentication_populates_context_and_blocks_missing_credentials() -> None:
    resolver = StaticApiKeyUserResolver({"key-1": ResolvedUser(user_id="service-1")})
    app = FastAPI()
    seen: list[dict[str, Any]] = []

    async def entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(payload)
        return await _entrypoint(payload)

    (
        HostingFactory(app)
        .add_agent(entrypoint, make_descriptor("demo-agent"))
        .add_ai_endpoints(EndpointSurface.OPENAI_RESPONSES)
        .add_security(AuthenticationPolicy.api_key(resolver))
        .register()
    )

    missing_key = asyncio.run(_request(app, "POST", "/v1/responses", json=_SURFACE_REQUESTS[0][2]))
    valid_key = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/responses",
            json=_SURFACE_REQUESTS[0][2],
            headers={"x-api-key": "key-1"},
        )
    )

    assert missing_key.status_code == 401
    assert valid_key.status_code == 200
    assert len(seen) == 1
    assert seen[0]["auth_context"]["userId"] == "service-1"


@pytest.mark.parametrize(
    "configure",
    [
        lambda app: HostingFactory(app),
        lambda app: HostingFactory(app)
        .add_agent(_entrypoint, make_descriptor("demo-agent"))
        .add_security(AuthenticationPolicy.anonymous()),
        lambda app: HostingFactory(app)
        .add_agent(_entrypoint, make_descriptor("demo-agent"))
        .add_ai_endpoints(EndpointSurface.OPENAI_RESPONSES),
    ],
)
def test_incomplete_factory_fails_without_mutating_fastapi_app(
    configure: Callable[[FastAPI], HostingFactory],
) -> None:
    app = FastAPI()
    original_routes = tuple(app.routes)
    factory = configure(app)

    with pytest.raises(HostingConfigurationError):
        factory.register()

    assert tuple(app.routes) == original_routes


def test_anonymous_factory_cannot_require_authentication_for_discovery() -> None:
    app = FastAPI()
    factory = _configured_factory(
        app,
        (EndpointSurface.OPENAI_RESPONSES,),
        discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=True),
    )
    original_routes = tuple(app.routes)

    with pytest.raises(HostingConfigurationError):
        factory.register()

    assert tuple(app.routes) == original_routes


def test_factory_rejects_duplicate_registration_without_adding_routes_twice() -> None:
    app = FastAPI()
    factory = _configured_factory(app, (EndpointSurface.OPENAI_RESPONSES,))
    factory.register()
    registered_routes = tuple(app.routes)

    with pytest.raises(HostingConfigurationError):
        factory.register()

    assert tuple(app.routes) == registered_routes


def test_discovery_routes_are_not_added_without_discovery_configuration() -> None:
    app = FastAPI()
    _configured_factory(app, (EndpointSurface.OPENAI_RESPONSES,)).register()

    response = asyncio.run(_request(app, "GET", "/v1/models"))

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("implementation", "protocol"),
    [
        (ApiKeyAuthenticator, Authenticator),
        (JwtAuthenticator, Authenticator),
        (StaticApiKeyUserResolver, ApiKeyUserResolver),
        (StaticSymmetricKeyResolver, JwtKeyResolver),
        (StaticPublicKeyResolver, JwtKeyResolver),
        (RotatingKeyResolver, JwtKeyResolver),
        (JwksKeyResolver, JwtKeyResolver),
        (DiscoveredJwksKeyResolver, JwtKeyResolver),
        (InMemoryAuditTrail, AuditTrail),
        (LoggingAuditTrail, AuditTrail),
        (RoleRequiredAccessPolicy, AgentAccessPolicy),
        (InMemoryPendingConfirmationStore, PendingConfirmationStore),
        (InMemoryConfirmationPreferenceStore, ConfirmationPreferenceStore),
        (ConfiguredConfirmationPolicy, ConfirmationPolicy),
        (UnattendedApprovalAuthority, ConfirmationAuthority),
        (DispatcherImpl, Dispatcher),
    ],
)
def test_runtime_protocol_implementations_declare_their_protocol(
    implementation: type[Any], protocol: type[Any]
) -> None:
    assert protocol in implementation.__bases__

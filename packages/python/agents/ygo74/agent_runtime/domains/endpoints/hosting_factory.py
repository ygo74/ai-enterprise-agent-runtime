"""Fluent setup for hosting one described agent with FastAPI."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any, Self

from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.configuration.agent_http_configuration import (
    AgentHttpRuntimeSettings,
)
from ygo74.agent_runtime.domains.contracts.http_configuration import (
    HttpEndpoint,
    McpHttpEndpointConfiguration,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import (
    _register_ai_endpoints,
)
from ygo74.agent_runtime.domains.endpoints.rate_limiting import RateLimitSettings
from ygo74.agent_runtime.domains.http.asgi_lifecycle import AsgiShutdownRegistrar
from ygo74.agent_runtime.domains.streaming.stream_processor import AgentInvocation

AgentEntrypoint = Callable[[dict[str, Any]], AgentInvocation]


class HostingConfigurationError(ValueError):
    """Raised when a hosting factory is incomplete or internally inconsistent."""


class EndpointSurface(StrEnum):
    """Invocation endpoint surfaces currently supported by the Python runtime."""
    OPENAI_RESPONSES = "openai.responses"
    OPENAI_CHAT_COMPLETIONS = "openai.chat_completions"
    ANTHROPIC_MESSAGES = "anthropic.messages"
    MCP = "mcp"


_HTTP_ENDPOINT_SURFACES: dict[HttpEndpoint, EndpointSurface] = {
    HttpEndpoint.CHAT_COMPLETIONS: EndpointSurface.OPENAI_CHAT_COMPLETIONS,
    HttpEndpoint.RESPONSES: EndpointSurface.OPENAI_RESPONSES,
    HttpEndpoint.MESSAGES: EndpointSurface.ANTHROPIC_MESSAGES,
    HttpEndpoint.MCP: EndpointSurface.MCP,
}


class HostingFactory:
    """Collect agent-hosting configuration, then register it on a FastAPI app.

    One factory owns one entrypoint and descriptor. Applications that route
    multiple agents can continue to supply their dispatcher and descriptor
    registry directly to :func:`add_ai_endpoints`.

    Routes are not added until :meth:`register` validates the full configuration.
    Authentication is mandatory and must be chosen explicitly; use
    :meth:`AuthenticationPolicy.anonymous` when open access is intentional.

    Args:
        app (Any): ASGI application receiving the configured agent routes.
    """
    def __init__(self, app: Any) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            app (Any): ASGI application receiving the configured agent routes.
        """
        self._app = app
        self._entrypoint: AgentEntrypoint | None = None
        self._descriptor: AgentDescriptor | None = None
        self._surfaces: frozenset[EndpointSurface] | None = None
        self._authentication: AuthenticationPolicy | None = None
        self._rate_limit: RateLimitSettings | None = None
        self._http_settings: AgentHttpRuntimeSettings | None = None
        self._mcp_resource_url: str | None = None
        self._discovery: DiscoveryConfiguration | None = None
        self._registered = False

    def add_agent(
        self, entrypoint: AgentEntrypoint, descriptor: AgentDescriptor
    ) -> Self:
        """Set the entrypoint and public descriptor for the hosted agent.

        Args:
            entrypoint (AgentEntrypoint): Application callback that handles the normalized request.
            descriptor (AgentDescriptor): The canonical agent descriptor whose identity and capabilities are used.
        """
        self._ensure_configurable()
        if self._entrypoint is not None or self._descriptor is not None:
            raise HostingConfigurationError(
                "an agent is already configured for this factory"
            )

        self._entrypoint = entrypoint
        self._descriptor = descriptor
        return self

    def add_ai_endpoints(self, *surfaces: EndpointSurface) -> Self:
        """Select which supported invocation routes the app will expose.

        Args:
            surfaces (EndpointSurface): Enabled endpoint and discovery surfaces used to validate capabilities.
        """
        self._ensure_configurable()
        if self._surfaces is not None:
            raise HostingConfigurationError(
                "AI endpoint surfaces are already configured for this factory"
            )
        if any(not isinstance(surface, EndpointSurface) for surface in surfaces):
            raise HostingConfigurationError(
                "AI endpoint surfaces must be EndpointSurface values"
            )
        if len(set(surfaces)) != len(surfaces):
            raise HostingConfigurationError(
                "AI endpoint surfaces must not contain duplicates"
            )

        self._surfaces = frozenset(surfaces)
        return self

    def add_security(self, policy: AuthenticationPolicy) -> Self:
        """Set the explicit invocation authentication policy.

        Args:
            policy (AuthenticationPolicy): Configured authentication or authorization policy.
        """
        self._ensure_configurable()
        if self._authentication is not None:
            raise HostingConfigurationError(
                "security is already configured for this factory"
            )

        self._authentication = policy
        return self

    def add_http_settings(self, settings: AgentHttpRuntimeSettings) -> Self:
        """Apply the resolved HTTP section of an agent manifest to this host.

        This method keeps endpoint selection and security sourced from one
        validated manifest object; hosts may still use the individual fluent
        methods for application-owned configuration.

        Args:
            settings: Runtime settings resolved from ``AgentManifest.http``.
        """
        self._ensure_configurable()
        if (
            self._surfaces is not None
            or self._authentication is not None
            or self._mcp_resource_url is not None
        ):
            raise HostingConfigurationError(
                "HTTP settings cannot be combined with separately configured endpoints or security"
            )
        self._surfaces = frozenset(
            _HTTP_ENDPOINT_SURFACES[endpoint] for endpoint in settings.endpoints
        )
        self._authentication = settings.authentication
        self._rate_limit = settings.rate_limit
        self._http_settings = settings
        return self

    def add_mcp_resource_url(self, resource_url: str) -> Self:
        """Set the canonical OAuth resource URL for a manually configured MCP surface.

        Manifest-backed hosts should set ``http.mcp.resource_url`` instead.

        Args:
            resource_url: Public HTTPS URL advertised for JWT-authenticated MCP.
        """
        self._ensure_configurable()
        if self._http_settings is not None or self._mcp_resource_url is not None:
            raise HostingConfigurationError(
                "the MCP resource URL is already configured or owned by HTTP settings"
            )
        configuration = McpHttpEndpointConfiguration(resource_url=resource_url)
        resolved = configuration.resource_url
        if resolved is None or resolved.startswith("${"):
            raise HostingConfigurationError(
                "a manually configured MCP resource URL must be a literal HTTPS URL"
            )
        self._mcp_resource_url = resolved
        return self

    def add_discovery(self, configuration: DiscoveryConfiguration) -> Self:
        """Enable provider model discovery with its own authentication setting.

        Args:
            configuration (DiscoveryConfiguration): Validated endpoint or discovery settings controlling this operation.
        """
        self._ensure_configurable()
        if self._discovery is not None:
            raise HostingConfigurationError(
                "discovery is already configured for this factory"
            )

        self._discovery = configuration
        return self

    def register(self) -> None:
        """Validate all options and register the selected routes exactly once."""
        if self._registered:
            raise HostingConfigurationError(
                "this hosting factory has already registered its routes"
            )

        entrypoint = self._entrypoint
        descriptor = self._descriptor
        surfaces = self._surfaces
        authentication = self._authentication

        if entrypoint is None or descriptor is None:
            raise HostingConfigurationError(
                "configure an agent entrypoint and descriptor before registration"
            )
        if not surfaces:
            raise HostingConfigurationError(
                "select at least one AI endpoint surface before registration"
            )
        if authentication is None:
            raise HostingConfigurationError(
                "configure an AuthenticationPolicy before registration; use "
                "AuthenticationPolicy.anonymous() for intentional open access"
            )
        if self._discovery is not None:
            if not self._discovery.any_model_surface_enabled:
                raise HostingConfigurationError(
                    "discovery configuration must enable OpenAI models, Anthropic models, or both"
                )
            if (
                self._discovery.require_authentication
                and not authentication.authenticators
            ):
                raise HostingConfigurationError(
                    "protected discovery requires an AuthenticationPolicy with at least one authenticator"
                )
        if not callable(getattr(self._app, "post", None)):
            raise HostingConfigurationError(
                "the configured app must support FastAPI POST route registration"
            )
        mcp_selected = EndpointSurface.MCP in surfaces
        if mcp_selected and not authentication.authenticators:
            raise HostingConfigurationError(
                "an MCP agent endpoint requires authenticated caller identity"
            )
        if self._http_settings is not None:
            router = getattr(self._app, "router", None)
            if router is None or not callable(
                getattr(router, "lifespan_context", None)
            ):
                raise HostingConfigurationError(
                    "the configured app must expose an ASGI shutdown lifecycle for manifest HTTP settings"
                )
        mcp_endpoint: Any | None = None
        mcp_host: Any | None = None
        if mcp_selected:
            if not callable(getattr(self._app, "mount", None)):
                raise HostingConfigurationError(
                    "the configured app must support ASGI mounting for MCP"
                )
            router = getattr(self._app, "router", None)
            if router is None or not callable(
                getattr(router, "lifespan_context", None)
            ):
                raise HostingConfigurationError(
                    "the configured app must expose an ASGI lifespan for MCP"
                )
            try:
                from ygo74.agent_runtime.domains.endpoints.mcp_agent_endpoint import (
                    McpAgentEndpoint,
                )
                from ygo74.agent_runtime.domains.mcpserver.host import McpServerHost
            except ImportError as error:
                raise HostingConfigurationError(
                    "the MCP endpoint requires the optional "
                    "'ygo74-agent-runtime-agents[mcp-server]' extra"
                ) from error
            resource_url = (
                self._http_settings.mcp_resource_url
                if self._http_settings is not None
                else self._mcp_resource_url
            )
            try:
                mcp_host = McpServerHost(
                    policy=authentication,
                    resource_url=resource_url or "",
                )
            except Exception as error:
                raise HostingConfigurationError(
                    f"MCP endpoint configuration is invalid: {type(error).__name__}"
                ) from error
            mcp_endpoint = McpAgentEndpoint(entrypoint, descriptor).build_server()
        if self._discovery is not None and not callable(
            getattr(self._app, "get", None)
        ):
            raise HostingConfigurationError(
                "the configured app must support FastAPI GET route registration for discovery"
            )

        descriptor_registry = DescriptorRegistry((descriptor,))
        web_surfaces = surfaces - {EndpointSurface.MCP}
        if web_surfaces or self._discovery is not None:
            _register_ai_endpoints(
                self._app,
                entrypoint,
                default_route_key=descriptor.route_key,
                enable_openai_responses=EndpointSurface.OPENAI_RESPONSES
                in web_surfaces,
                enable_openai_chat_completions=EndpointSurface.OPENAI_CHAT_COMPLETIONS
                in web_surfaces,
                enable_anthropic_messages=EndpointSurface.ANTHROPIC_MESSAGES
                in web_surfaces,
                require_bearer_token=authentication.requires_authentication,
                authenticators=authentication.authenticators,
                descriptor_registry=descriptor_registry,
                discovery=self._discovery,
                rate_limit_settings=self._rate_limit,
            )
        if mcp_selected:
            assert mcp_endpoint is not None and mcp_host is not None
            mcp_host.mount(
                self._app,
                mcp_endpoint,
                close_authenticator=self._http_settings is None,
            )
        if self._http_settings is not None:
            AsgiShutdownRegistrar.register(
                self._app, self._http_settings.close, wrap_lifespan=True
            )
        self._registered = True

    def _ensure_configurable(self) -> None:
        """Refuse changes after route registration."""
        if self._registered:
            raise HostingConfigurationError(
                "hosting configuration cannot change after registration"
            )

"""Operator-owned local single-deployment worker, independent of agent SDKs."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from typing import Any, cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_definition import AgentDefinition
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.conversation_entrypoint import (
    ConversationEntrypoint,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import (
    EndpointSurface,
    HostingFactory,
)
from ygo74.agent_runtime.domains.sessions.agent_conversation import (
    ConversationPort,
    HttpConversationEngine,
)
from ygo74.agent_runtime.domains.sessions.conversation_cache import (
    ConversationRuntimeCache,
)


class TrustedFactoryLoader:
    """Load a factory only from a definition supplied by deployment configuration."""

    @staticmethod
    def load(definition: AgentDefinition) -> Callable[..., object]:
        """Import an admitted export; never consumes request payloads.

        Args:
            definition: Validated operator-selected agent definition.
        """
        module_name, export = definition.factory.split(":")
        factory = getattr(import_module(module_name), export)
        if not callable(factory):
            raise TypeError("native factory export is not callable")
        return cast(Callable[..., object], factory)


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    """Deployment configuration owned by the runtime operator.

    Args:
        deployment_id: Stable deployment partition, one per process.
        identity_namespace: Verified issuer/tenant partition selected by operator.
        authentication: Explicit authentication; anonymous hosting is refused.
        surfaces: Enabled invocation endpoints.
        discovery: Operator-selected discovery access and surfaces.
        max_conversations: Cache capacity.
        idle_lifetime: Expiry after last completed lease.
        turn_timeout: Bounded execution including native approval rounds.
    """

    deployment_id: str
    identity_namespace: str
    authentication: AuthenticationPolicy
    surfaces: tuple[EndpointSurface, ...] = tuple(EndpointSurface)
    discovery: DiscoveryConfiguration | None = None
    max_conversations: int = 200
    idle_lifetime: timedelta = timedelta(minutes=30)
    turn_timeout: float = 120

    def __post_init__(self) -> None:
        """Refuse missing identity boundaries, nonpositive limits and open hosts."""
        if not self.deployment_id or not self.identity_namespace:
            raise ValueError("worker requires deployment and identity namespace")
        if not self.authentication.authenticators:
            raise ValueError("managed worker requires verified authentication")
        if self.max_conversations < 1 or self.turn_timeout <= 0 or self.idle_lifetime <= timedelta(0):
            raise ValueError("worker lifecycle limits must be positive")


class ManagedAgentWorker:
    """Compose the existing host, cache and conversation engine for one deployment.

    Args:
        definition: Admitted declarative definition using existing discovery metadata.
        settings: Operator security, endpoints and lifecycle configuration.
        conversation_factory: Binding-owned native composition or optional advanced bridge.
    """

    def __init__(self, definition: AgentDefinition, settings: WorkerSettings,
                 conversation_factory: Callable[[AgentPrincipal, str], Awaitable[ConversationPort]]) -> None:
        """Create a worker without adding a framework dependency to the core.

        Args:
            definition: Trusted agent declaration.
            settings: Operator controls.
            conversation_factory: Typed binding factory, not selected by a request.
        """
        self.definition, self.settings = definition, settings
        self.conversations = ConversationRuntimeCache(
            conversation_factory, self._close,
            max_conversations=settings.max_conversations, idle_lifetime=settings.idle_lifetime,
            identity_namespace=f"{settings.deployment_id}:{settings.identity_namespace}",
            hard_capacity=True,
        )
        self._entrypoint = ConversationEntrypoint(
            HttpConversationEngine(self.conversations), require_email=definition.require_email,
        )
        self._ready = False

    @staticmethod
    async def _close(conversation: ConversationPort) -> None:
        """Release binding-owned native resources.

        Args:
            conversation: Retired conversation.
        """
        await conversation.aclose()

    def build_app(self, *, title: str | None = None) -> FastAPI:
        """Expose operator-selected endpoints with graceful lifecycle.

        Args:
            title: Optional local service display name.
        """
        app = FastAPI(title=title or self.definition.descriptor.display_name, lifespan=self._lifespan)
        app.state.conversations = self.conversations
        app.state.worker = self
        host = HostingFactory(app).add_agent(self._invoke, self.definition.descriptor)
        host.add_ai_endpoints(*self.settings.surfaces).add_security(self.settings.authentication)
        if self.settings.discovery is not None:
            host.add_discovery(self.settings.discovery)
        host.register()
        app.get("/health/ready")(self._readiness)
        return app

    async def _invoke(self, payload: dict[str, Any]) -> StandardExchangeResponse | AsyncIterator[AgentStreamEvent]:
        """Apply operator timeouts to both native modes at the boundary.

        Args:
            payload: Authenticated normalized endpoint payload.
        """
        async with asyncio.timeout(self.settings.turn_timeout):
            result = await self._entrypoint(payload)
        if not isinstance(result, StandardExchangeResponse):
            return self._stream(result)
        return result

    async def _stream(self, producer: AsyncIterator[AgentStreamEvent]) -> AsyncGenerator[AgentStreamEvent]:
        """Bound a full streamed turn and always close its producer.

        Args:
            producer: Native conversation stream.
        """
        async with asyncio.timeout(self.settings.turn_timeout):
            close = getattr(producer, "aclose", None)
            try:
                async for event in producer:
                    yield event
            finally:
                if close is not None:
                    await close()

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        """Mark readiness then stop admission, drain leases and close scopes.

        Args:
            app: FastAPI application whose lifecycle owns the worker.
        """
        self._ready = True
        try:
            yield
        finally:
            self._ready = False
            await self.conversations.aclose()

    async def _readiness(self) -> JSONResponse:
        """Report local process readiness without identity or deployment secrets."""
        return JSONResponse({"ready": self._ready}, status_code=200 if self._ready else 503)

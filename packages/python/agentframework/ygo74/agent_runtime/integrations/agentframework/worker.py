"""Native factory composition for the platform's managed reference worker."""

import inspect
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from dataclasses import dataclass

from agent_framework import Agent, InMemoryHistoryProvider, SupportsAgentRun
from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.contracts.agent_definition import (
    AgentDefinition,
    AgentFactoryContext,
)
from ygo74.agent_runtime.domains.endpoints.managed_worker import (
    ManagedAgentWorker,
    TrustedFactoryLoader,
    WorkerSettings,
)
from ygo74.agent_runtime.domains.humanapproval.commands import ConfirmationCommand
from ygo74.agent_runtime.domains.humanapproval.pending_renderer import (
    PendingConfirmationRenderer,
)
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    InMemoryPendingConfirmationStore,
    UnknownTicketError,
)
from ygo74.agent_runtime.domains.security.user_context import UserContext
from ygo74.agent_runtime.domains.sessions.agent_conversation import (
    AgentConversation,
    ConversationPort,
)

from .binding import AgentFrameworkSession


@dataclass(slots=True)
class _NativeResources:
    """Conversation scope, with no authorization inferred from native output.

    Args:
        user: Verified identity without any granted tool permissions.
        scope: Factory dependency scope owned by this conversation.
    """

    user: UserContext
    scope: AsyncExitStack

    async def aclose(self) -> None:
        """Close native factory dependencies exactly once."""
        await self.scope.aclose()


class _NoConfirmations:
    """Reject replay commands for native agents without a ticket bridge."""

    async def run(self, command: ConfirmationCommand) -> str:
        """Refuse commands that cannot correspond to a stored ticket.

        Args:
            command: Parsed confirmation command.
        """
        raise UnknownTicketError(command.ticket_id)


class AgentFrameworkWorker:
    """Simple BYOA path: a native factory and definition, plus operator settings.

    Args:
        definition: Trusted native export and declarative identity/capabilities.
        settings: Operator deployment/authentication/lifecycle configuration.
        admission: Optional trusted deterministic tool-policy validation hook.
        factory: Optional already-resolved native factory from trusted composition.
    """

    def __init__(
        self, definition: AgentDefinition, settings: WorkerSettings, *,
        admission: Callable[[AgentDefinition, SupportsAgentRun], None] | None = None,
        factory: Callable[[AgentFactoryContext], object] | None = None,
    ) -> None:
        """Validate registration before any routes become available.

        Args:
            definition: Validated deployment definition.
            settings: Runtime operator controls.
            admission: Required for native tools; checks actual enforceable gates.
            factory: Trusted DI override, never taken from request data.
        """
        if definition.tools and admission is None:
            raise ValueError("native tools require an enforceable admission policy")
        self._definition, self._settings, self._admission = definition, settings, admission
        self._factory = factory or TrustedFactoryLoader.load(definition)
        self.worker = ManagedAgentWorker(definition, settings, self._build)

    def build_app(self) -> FastAPI:
        """Build the platform-owned HTTP worker, not an agent-owned server."""
        return self.worker.build_app()

    async def _build(self, principal: AgentPrincipal, conversation_id: str) -> ConversationPort:
        """Resolve a native agent with standard async dependency scopes.

        Args:
            principal: Verified caller associated with every factory dependency.
            conversation_id: Caller-scoped history identifier.
        """
        if self._definition.require_email and not principal.email:
            raise ValueError("native agent requires verified email")
        context = AgentFactoryContext(principal, conversation_id, self._settings.deployment_id,
                                      self._settings.identity_namespace)
        scope = AsyncExitStack()
        try:
            resource = self._factory(context)
            if inspect.isawaitable(resource):
                resource = await resource
            if isinstance(resource, AbstractAsyncContextManager):
                resource = await scope.enter_async_context(resource)
            if not isinstance(resource, SupportsAgentRun):
                raise TypeError("native factory must return a runnable native agent or an async scope yielding one")
            self._validate_agent(resource)
            return AgentConversation(
                _NativeResources(UserContext(user_id=principal.subject, session_id=conversation_id), scope),
                AgentFrameworkSession(resource, session_id=conversation_id,
                                      tool_names=tuple(tool.tool_name for tool in self._definition.tools)),
                InMemoryPendingConfirmationStore(), _NoConfirmations(), conversation_id, PendingConfirmationRenderer(),
            )
        except BaseException:
            await scope.aclose()
            raise

    def _validate_agent(self, agent: SupportsAgentRun) -> None:
        """Reject undeclared native tools; declarations never grant permission.

        Args:
            agent: Factory output to check at the binding boundary.
        """
        if not isinstance(agent, Agent):
            if self._admission is None:
                raise ValueError("custom native agents require an explicit capability admission policy")
            self._admission(self._definition, agent)
            return
        # Only the exact SDK history implementation has a known static surface.
        # Other providers (including subclasses) can inject tools or middleware.
        dynamic_context = any(type(provider) is not InMemoryHistoryProvider for provider in agent.context_providers)
        if dynamic_context and self._admission is None:
            raise ValueError("dynamic context providers require an explicit capability admission policy")
        options = agent.default_options
        native_tools = options.get("tools") or []
        names = {getattr(tool, "name", None) for tool in native_tools}
        declared = {tool.tool_name for tool in self._definition.tools}
        if names != declared:
            raise ValueError("native tools do not match admitted declarations")
        if names and self._admission is None:
            raise ValueError("native tools have no enforceable control point")
        if self._admission is not None:
            self._admission(self._definition, agent)

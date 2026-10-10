"""Optional HTTP worker facade for native LangGraph agents."""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from typing import cast

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

from .native import LangGraphRunnable, LangGraphSession


class _NativeResources:
    """Own one factory scope and the authenticated identity for a conversation."""

    def __init__(self, user: UserContext, scope: AsyncExitStack) -> None:
        """Retain resources whose lifetime matches the conversation cache entry."""
        self.user = user
        self._scope = scope

    async def aclose(self) -> None:
        """Close factory-owned resources once the conversation is retired."""
        await self._scope.aclose()


class _NoTicketRunner:
    """Reject confirmation commands when an application supplied no ticket bridge."""

    async def run(self, command: ConfirmationCommand) -> str:
        """Report that the requested ticket does not exist in this simple worker."""
        raise UnknownTicketError(command.ticket_id)


ConversationFactory = Callable[[AgentPrincipal, str], Awaitable[ConversationPort]]
GraphFactory = Callable[[AgentFactoryContext], object]
GraphAdmission = Callable[[AgentDefinition, LangGraphRunnable], None]


class LangGraphWorker:
    """Build a managed worker from a trusted graph factory or app conversation factory.

    Args:
        definition: Trusted descriptor and import path selected by deployment.
        settings: Operator-owned authentication, endpoint and lifecycle settings.
        admission: Optional deterministic hook that checks a graph's actual tool surface.
        factory: Optional dependency-injected graph factory, never selected from requests.
        conversation_factory: Advanced application-owned factory for domain approvals/resources.
    """

    def __init__(
        self,
        definition: AgentDefinition,
        settings: WorkerSettings,
        *,
        admission: GraphAdmission | None = None,
        factory: GraphFactory | None = None,
        conversation_factory: ConversationFactory | None = None,
    ) -> None:
        """Compose the framework binding with the shared managed worker."""
        if conversation_factory is None and definition.tools and admission is None:
            raise ValueError("native tools require an enforceable admission policy")
        self._definition = definition
        self._settings = settings
        self._admission = admission
        self._factory = factory or cast(GraphFactory, TrustedFactoryLoader.load(definition))
        build = conversation_factory or self._build_conversation
        self.worker = ManagedAgentWorker(definition, settings, build)

    def build_app(self) -> FastAPI:
        """Create the standard authenticated HTTP, discovery and readiness surfaces."""
        return self.worker.build_app()

    async def _build_conversation(self, principal: AgentPrincipal, conversation_id: str) -> ConversationPort:
        """Resolve a graph factory inside a conversation-owned async resource scope."""
        context = AgentFactoryContext(
            principal,
            conversation_id,
            self._settings.deployment_id,
            self._settings.identity_namespace,
        )
        scope = AsyncExitStack()
        try:
            produced = self._factory(context)
            if inspect.isawaitable(produced):
                produced = await produced
            if isinstance(produced, AbstractAsyncContextManager):
                produced = await scope.enter_async_context(produced)
            if not _is_graph(produced):
                raise TypeError("LangGraph factory must return a graph or async scope yielding one")
            graph = cast(LangGraphRunnable, produced)
            self._validate_graph(graph)
            user = UserContext(user_id=principal.subject, session_id=conversation_id)
            return AgentConversation(
                _NativeResources(user, scope),
                LangGraphSession(graph, thread_id=_thread_id(context)),
                InMemoryPendingConfirmationStore(),
                _NoTicketRunner(),
                conversation_id,
                PendingConfirmationRenderer(),
            )
        except BaseException:
            await scope.aclose()
            raise

    def _validate_graph(self, graph: LangGraphRunnable) -> None:
        """Require a trusted admission hook for tools outside a provable static surface."""
        if self._admission is not None:
            self._admission(self._definition, graph)
            return
        inspect_graph = getattr(graph, "get_graph", None)
        if not callable(inspect_graph):
            raise TypeError("custom LangGraph instances require an explicit capability admission policy")
        snapshot = inspect_graph()
        nodes = getattr(snapshot, "nodes", None)
        if not isinstance(nodes, Mapping):
            raise TypeError("LangGraph tool surface cannot be inspected without an admission policy")
        tool_node = next((getattr(node, "data", None) for node in nodes.values()
                          if _is_tool_node(getattr(node, "data", None))), None)
        if tool_node is not None:
            actual = _tool_names(tool_node)
            declared = {tool.tool_name for tool in self._definition.tools}
            if not actual or actual != declared:
                raise ValueError("LangGraph tools do not match admitted declarations")
            if actual:
                raise ValueError("LangGraph tools require an enforceable admission policy")
        if self._definition.tools:
            raise ValueError("declared native tools were not found in the graph surface")


def _is_graph(value: object) -> bool:
    """Check only the public async graph methods used by this binding."""
    return callable(getattr(value, "ainvoke", None)) and callable(getattr(value, "astream_events", None))


def _is_tool_node(value: object) -> bool:
    """Recognize LangGraph's public ToolNode without importing extra tool modules."""
    return type(value).__name__ == "ToolNode"


def _tool_names(node: object) -> set[str]:
    """Extract a statically inspectable ToolNode surface for declaration comparison."""
    tools = getattr(node, "tools_by_name", None)
    if isinstance(tools, Mapping):
        return {str(name) for name in tools}
    values = getattr(node, "tools", None)
    if isinstance(values, Mapping):
        return {str(name) for name in values}
    if isinstance(values, (tuple, list)):
        return {name for item in values if isinstance((name := getattr(item, "name", None)), str)}
    return set()


def _thread_id(context: AgentFactoryContext) -> str:
    """Derive an opaque graph checkpoint key from the verified identity partition."""
    parts = (
        context.deployment_id,
        context.identity_namespace,
        context.principal.subject,
        context.conversation_id,
    )
    material = "".join(f"{len(part)}:{part}" for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()

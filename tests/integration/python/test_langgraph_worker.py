"""Managed-worker tests for conversation scoping and LangGraph identity partitioning."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from langchain_core.runnables.schema import StreamEvent
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_definition import (
    AgentDefinition,
    AgentFactoryContext,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)
from ygo74.agent_runtime.domains.endpoints.managed_worker import WorkerSettings
from ygo74.agent_runtime.integrations.langchain.worker import LangGraphWorker


class GraphFake:
    """Minimal public async graph with an inspectable empty tool surface."""

    def get_graph(self) -> SimpleNamespace:
        """Expose an empty node map proving the graph has no tools."""
        return SimpleNamespace(nodes={})

    async def ainvoke(self, value: object, *, config: Mapping[str, Any]) -> object:
        """Return a deterministic empty state; invocation is not needed here."""
        del value, config
        return {"messages": []}

    def astream_events(
        self,
        value: object,
        *,
        config: Mapping[str, Any],
        version: str,
    ) -> AsyncIterator[StreamEvent]:
        """Return an empty native stream for the binding protocol."""
        del value, config, version

        async def no_events() -> AsyncIterator[StreamEvent]:
            if False:
                yield cast(StreamEvent, None)

        return no_events()


def _definition() -> AgentDefinition:
    """Build a minimal authenticated, tool-free worker definition."""
    descriptor = AgentDescriptor(
        agent_id="graph-demo",
        route_key="graph-demo",
        display_name="Graph demo",
        description="Offline LangGraph worker example.",
        version="1.0.0",
        owner="tests",
        created_at_utc=datetime.now(UTC),
        capabilities=AgentCapabilitySet(),
    )
    return AgentDefinition(descriptor, "tests.graph:build")


def _settings() -> WorkerSettings:
    """Provide explicit operator authentication and identity namespace."""
    authentication = AuthenticationPolicy.api_key(
        StaticApiKeyUserResolver({"local": ResolvedUser(user_id="demo")})
    )
    return WorkerSettings("tests", "issuer", authentication)


@pytest.mark.asyncio
async def test_scoped_graph_closes_with_its_conversation_and_is_identity_partitioned() -> None:
    """A factory scope is released, and identical caller conversation IDs do not collide."""
    closed: list[str] = []

    def factory(context: AgentFactoryContext) -> object:
        """Create a scoped fake graph for each trusted context."""
        subject = context.principal.subject

        @asynccontextmanager
        async def scope() -> AsyncIterator[GraphFake]:
            try:
                yield GraphFake()
            finally:
                closed.append(subject)

        return scope()

    worker = LangGraphWorker(_definition(), _settings(), factory=factory)
    diana = await worker._build_conversation(AgentPrincipal(subject="diana"), "same-conversation")
    alice = await worker._build_conversation(AgentPrincipal(subject="alice"), "same-conversation")

    diana_thread = diana.session.thread_id
    alice_thread = alice.session.thread_id
    assert diana_thread != alice_thread
    assert "same-conversation" not in diana_thread
    await diana.aclose()
    await alice.aclose()

    assert closed == ["diana", "alice"]


def test_tool_declarations_need_an_explicit_admission_hook() -> None:
    """Metadata cannot by itself authorize native tool execution."""
    from ygo74.agent_runtime.domains.security.operations import (
        OperationType,
        RiskLevel,
        ToolOperationDescriptor,
    )
    from ygo74.agent_runtime.domains.security.permissions import Permission

    declared = ToolOperationDescriptor(
        tool_name="write_page",
        operation_type=OperationType.WRITE,
        risk_level=RiskLevel.HIGH,
        required_permission=Permission("wiki", "write"),
        confirmation_required_by_default=True,
    )
    descriptor = _definition().descriptor
    tool_descriptor = replace(descriptor, capabilities=AgentCapabilitySet(tool_invocation=True))
    tool_definition = AgentDefinition(
        tool_descriptor,
        "tests.graph:build",
        tools=(declared,),
        control_point="tests",
    )

    with pytest.raises(ValueError, match="admission policy"):
        LangGraphWorker(tool_definition, _settings())

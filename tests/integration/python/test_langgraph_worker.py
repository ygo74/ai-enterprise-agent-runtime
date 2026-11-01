"""Managed-worker tests for conversation scoping and LangGraph identity partitioning."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from langchain_core.runnables.schema import StreamEvent
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.configuration.agent_http_configuration import (
    AgentHttpSettingsBuilder,
)
from ygo74.agent_runtime.domains.contracts.agent_definition import (
    AgentDefinition,
    AgentFactoryContext,
)
from ygo74.agent_runtime.domains.contracts.http_configuration import (
    AgentHttpConfiguration,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
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
async def test_managed_worker_registers_routes_and_security_from_manifest_settings() -> None:
    """Apply manifest HTTP settings while retaining worker lifecycle routes."""
    manifest_http = AgentHttpConfiguration.model_validate(
        {
            "endpoints": ["chat_completions"],
            "security": {
                "mode": "api_key",
                "api_key": {
                    "value": "${TEST_HTTP_API_KEY}",
                    "user": {"subject": "manifest-user"},
                },
            },
            "rate_limit": {"limits": ["60/minute"]},
        }
    )
    http_settings = AgentHttpSettingsBuilder(
        {"TEST_HTTP_API_KEY": "local-manifest-key"}
    ).build(manifest_http)
    settings = WorkerSettings(
        deployment_id="tests",
        identity_namespace="manifest-user",
        discovery=DiscoveryConfiguration(
            enable_openai_models=True,
            require_authentication=True,
        ),
        http_settings=http_settings,
    )
    worker = LangGraphWorker(_definition(), settings, factory=lambda _: GraphFake())

    app = worker.build_app()
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        unauthenticated = await client.get("/v1/models")
        models = await client.get(
            "/v1/models", headers={"x-api-key": "local-manifest-key"}
        )
        responses = await client.post("/v1/responses", json={})
        messages = await client.post("/v1/messages", json={})

        assert unauthenticated.status_code == 401
        assert models.status_code == 200
        assert models.json()["data"][0]["id"] == "graph-demo"
        assert responses.status_code == 404
        assert messages.status_code == 404


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

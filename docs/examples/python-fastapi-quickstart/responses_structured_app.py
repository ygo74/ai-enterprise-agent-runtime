"""Offline typed-output demo; the runtime owns all provider wire envelopes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    ImageContent,
    Notification,
    TextContent,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
)
from ygo74.agent_runtime.domains.contracts.media_content import EncodedMedia
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    TextDelta,
    ToolArgumentsDelta,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
    Modality,
)
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.conversation_payloads import latest_message
from ygo74.agent_runtime.domains.endpoints.hosting_factory import (
    EndpointSurface,
    HostingFactory,
)


class DemoScenario(StrEnum):
    DEFAULT = "default"
    RAG = "test:rag"
    CONTENT = "test:content"
    TOOLS = "test:tools"
    NOTIFICATIONS = "test:notifications"
    MEDIA = "test:media"


class StructuredDemo:
    def scenario(self, incoming: object) -> DemoScenario:
        command = latest_message(incoming)
        return next((scenario for scenario in DemoScenario if command == scenario.value), DemoScenario.DEFAULT)

    def output(self, scenario: DemoScenario) -> AgentOutput:
        if scenario is DemoScenario.RAG:
            return AgentOutput((TextContent(
                "Keep an audit journal for 30 days [1] and restrict access [2].\n"
                "[1] https://example.com/operations\n[2] https://example.com/security"
            ),))
        if scenario is DemoScenario.CONTENT:
            return AgentOutput((
                TextContent("Architecture overview."),
                TextContent("Operations: https://example.com/operations"),
                TextContent("Security: https://example.com/security"),
            ))
        if scenario is DemoScenario.TOOLS:
            return AgentOutput((
                ToolCallContent("retention-lookup", "lookup_retention", {"query": "journal retention"},
                                ToolExecution.INTERNAL),
                ToolResultContent("retention-lookup", "lookup_retention", {"retention_days": 30}),
                TextContent("The local fixture retains journals for 30 days."),
            ))
        if scenario is DemoScenario.MEDIA:
            return AgentOutput((
                TextContent("A one-pixel PNG fixture; no remote fetch or transcoding."),
                ImageContent(EncodedMedia(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=",
                    "image/png",
                )),
            ))
        if scenario is DemoScenario.NOTIFICATIONS:
            return AgentOutput((TextContent("The local fixture is ready."),))
        return AgentOutput((TextContent("A provider-neutral structured answer."),))

    async def stream(self, scenario: DemoScenario) -> AsyncIterator[AgentStreamEvent]:
        if scenario is DemoScenario.NOTIFICATIONS:
            yield ContentEvent("progress", Notification("Checking the local fixture."))
        for index, content in enumerate(self.output(scenario).contents):
            content_id = f"content-{index}"
            if isinstance(content, ToolCallContent):
                yield ContentStart(content_id, ToolCallContent(
                    content.call_id, content.name, {}, content.execution,
                ))
                yield ToolArgumentsDelta(content_id, '{"query":')
                yield ToolArgumentsDelta(content_id, '"journal retention"}')
                yield ContentEnd(content_id)
                continue
            if isinstance(content, TextContent):
                yield ContentStart(content_id, TextContent(""))
                midpoint = len(content.text) // 2
                yield TextDelta(content_id, content.text[:midpoint])
                yield TextDelta(content_id, content.text[midpoint:])
                yield ContentEnd(content_id)
                continue
            yield ContentEvent(content_id, content)
        yield TerminalEvent()


demo = StructuredDemo()


async def structured_agent(payload: dict[str, Any]) -> AgentOutput | AsyncIterator[AgentStreamEvent]:
    scenario = demo.scenario(payload.get("input"))
    if payload.get("stream") is True:
        return demo.stream(scenario)
    return demo.output(scenario)


app = FastAPI(title="Provider-neutral Structured Output Demo")
descriptor = AgentDescriptor(
    agent_id="structured-agent",
    route_key="structured-agent",
    display_name="Structured Demo Agent",
    description="Offline typed text, internal tool observations, progress notices and an unsupported image pivot fixture.",
    version="1.0.0",
    owner="quickstart",
    created_at_utc=datetime.now(UTC),
    capabilities=AgentCapabilitySet(streaming=True, output_modalities=(Modality.TEXT,)),
)
(
    HostingFactory(app)
    .add_agent(structured_agent, descriptor)
    .add_ai_endpoints(
        EndpointSurface.OPENAI_RESPONSES,
        EndpointSurface.OPENAI_CHAT_COMPLETIONS,
        EndpointSurface.ANTHROPIC_MESSAGES,
    )
    .add_security(AuthenticationPolicy.anonymous())
    .add_discovery(DiscoveryConfiguration(enable_openai_models=True))
    .register()
)

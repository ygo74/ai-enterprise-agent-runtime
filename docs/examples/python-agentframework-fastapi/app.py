"""Offline Agent Framework SDK output hosted through the runtime."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from agent_framework import (
    AgentResponse,
    AgentResponseUpdate,
    Content,
    Message,
    UsageDetails,
)
from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import (
    EndpointSurface,
    HostingFactory,
)
from ygo74.agent_runtime.integrations.agentframework import (
    AgentFrameworkOutputAdapter,
    AgentFrameworkStreamAdapter,
    ConversionDecision,
    ConversionStatus,
)

logger = logging.getLogger(__name__)


class OfflineAgent:
    """Synthetic real SDK values; no inference, credentials, or network calls."""

    @staticmethod
    def _usage_fixture() -> UsageDetails:
        """Known zero model consumption: this producer performs no inference."""
        return {"input_token_count": 0, "output_token_count": 0, "total_token_count": 0}

    @staticmethod
    def _inspect(decisions: tuple[ConversionDecision, ...]) -> None:
        for decision in decisions:
            if decision.status is not ConversionStatus.CONVERTED:
                logger.info("SDK output selection: type=%s status=%s reason=%s",
                            decision.native_type, decision.status, decision.reason)

    async def handle(self, payload: dict[str, JsonValue]) -> AgentOutput | AsyncIterator[AgentStreamEvent]:
        text = self._input_text(payload["input"])
        if payload.get("stream") is True:
            return self._stream(text)
        response = AgentResponse(
            messages=Message("assistant", [Content.from_text(f"Echo: {text}")]),
            finish_reason="stop",
            usage_details=self._usage_fixture(),
        )
        converted = AgentFrameworkOutputAdapter().convert(response)
        self._inspect(converted.decisions)
        return converted.output

    @classmethod
    def _input_text(cls, value: JsonValue) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return " ".join(text for item in value if (text := cls._input_text(item)))
        if isinstance(value, dict):
            return cls._input_text(value.get("content", value.get("text")))
        return ""

    async def _stream(self, text: str) -> AsyncIterator[AgentStreamEvent]:
        adapter = AgentFrameworkStreamAdapter()
        initial = adapter.convert_update(AgentResponseUpdate(
            contents=[Content.from_usage(self._usage_fixture())],
        ))
        self._inspect(initial.decisions)
        for event in initial.events:
            yield event
        for fragment in ("Echo: ", text):
            update = AgentResponseUpdate(
                message_id="offline-answer", role="assistant", contents=[Content.from_text(fragment)],
            )
            converted = adapter.convert_update(update)
            self._inspect(converted.decisions)
            for event in converted.events:
                yield event
        for event in adapter.finish():
            yield event


def create_app() -> FastAPI:
    app = FastAPI(title="Offline Microsoft Agent Framework integration")
    agent = OfflineAgent()
    descriptor = AgentDescriptor(
        agent_id="agentframework-echo",
        route_key="agentframework-echo",
        display_name="Agent Framework Echo",
        description="Offline demonstration using real Microsoft Agent Framework output types.",
        version="1.0.0",
        owner="example",
        created_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        capabilities=AgentCapabilitySet(streaming=True),
    )
    (
        HostingFactory(app)
        .add_agent(agent.handle, descriptor)
        .add_ai_endpoints(
            EndpointSurface.OPENAI_CHAT_COMPLETIONS,
            EndpointSurface.OPENAI_RESPONSES,
            EndpointSurface.ANTHROPIC_MESSAGES,
        )
        .add_security(AuthenticationPolicy.anonymous())
        .add_discovery(DiscoveryConfiguration(enable_openai_models=True))
        .register()
    )
    return app


app = create_app()

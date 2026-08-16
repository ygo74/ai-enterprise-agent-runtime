"""Shared helpers for the discovery integration tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI

from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
    AgentSkill,
    DiscoveryVisibility,
)
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_discovery_endpoints

ANTHROPIC_HEADERS = {"anthropic-version": "2023-06-01"}
FIXED_CREATED_AT = datetime(2026, 8, 16, tzinfo=timezone.utc)


def make_descriptor(
    agent_id: str,
    *,
    visibility: DiscoveryVisibility = DiscoveryVisibility.LISTED,
    streaming: bool = False,
) -> AgentDescriptor:
    """Build a fully populated descriptor so projections have something to render."""

    return AgentDescriptor(
        agent_id=agent_id,
        route_key=f"route-{agent_id}",
        display_name=f"{agent_id} display",
        description=f"Agent {agent_id}.",
        version="1.0.0",
        owner="platform-team",
        created_at_utc=FIXED_CREATED_AT,
        capabilities=AgentCapabilitySet(streaming=streaming),
        tags=("support",),
        skills=(AgentSkill(skill_id="faq", name="FAQ", description="Answers questions."),),
        security_schemes=("jwt",),
        discovery_visibility=visibility,
    )


def both_dialects_enabled() -> DiscoveryConfiguration:
    return DiscoveryConfiguration(enable_openai_models=True, enable_anthropic_models=True)


@dataclass(slots=True)
class DiscoveryHarness:
    """A FastAPI app wired to a descriptor registry, with a synchronous GET helper."""

    app: FastAPI

    @classmethod
    def build(
        cls,
        descriptors: list[AgentDescriptor],
        configuration: DiscoveryConfiguration | None = None,
    ) -> DiscoveryHarness:
        app = FastAPI()
        add_discovery_endpoints(
            app,
            DescriptorRegistry(descriptors),
            configuration or both_dialects_enabled(),
        )
        return cls(app)

    def get(self, path: str, headers: dict[str, str] | None = None) -> httpx.Response:
        async def _call() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.get(path, headers=headers)

        return asyncio.run(_call())

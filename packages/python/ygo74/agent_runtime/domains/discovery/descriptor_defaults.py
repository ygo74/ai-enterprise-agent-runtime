"""Defaulting rules that guarantee no exposed agent is silently undiscoverable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AGENT_ID_MAX_LENGTH,
    AgentCapabilitySet,
    AgentDescriptor,
)
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors

_UNSAFE_AGENT_ID_CHARS = re.compile(r"[^A-Za-z0-9._:-]")
_LEADING_UNSAFE = re.compile(r"^[^A-Za-z0-9]+")

DEFAULT_OWNER = "agent-runtime"
DEFAULT_VERSION = "1.0.0"


@dataclass(slots=True)
class DescriptorDefaults:
    """Builds the minimal derived descriptor for a handler registered without one.

    The derived descriptor is deliberately conservative: it advertises only the
    identity that can be inferred from the route key plus whatever capabilities
    the caller states explicitly, so discovery never over-promises.
    """

    owner: str = DEFAULT_OWNER
    version: str = DEFAULT_VERSION
    created_at_utc: datetime | None = None

    def derive(
        self,
        route_key: str,
        *,
        capabilities: AgentCapabilitySet | None = None,
    ) -> AgentDescriptor:
        """Build a minimal descriptor for ``route_key``."""

        agent_id = self.agent_id_for(route_key)
        return AgentDescriptor(
            agent_id=agent_id,
            route_key=route_key,
            display_name=agent_id,
            description=f"Agent exposed on route '{route_key}'.",
            version=self.version,
            owner=self.owner,
            created_at_utc=self.created_at_utc or datetime.now(tz=timezone.utc),
            capabilities=capabilities or AgentCapabilitySet(),
        )

    @staticmethod
    def agent_id_for(route_key: str) -> str:
        """Project a route key onto an identifier safe for a path segment and a model field."""

        candidate = _UNSAFE_AGENT_ID_CHARS.sub("-", route_key.strip())
        candidate = _LEADING_UNSAFE.sub("", candidate)[:AGENT_ID_MAX_LENGTH]
        if not candidate:
            raise DiscoveryErrors.invalid_descriptor(
                "routeKey",
                f"'{route_key}' cannot be projected onto a valid agentId; declare a descriptor explicitly",
            )
        return candidate

    def complete(self, descriptor: AgentDescriptor) -> AgentDescriptor:
        """Return the descriptor unchanged; declared descriptors are already complete.

        Kept as the single defaulting entry point so callers never branch on
        whether a descriptor was declared or derived.
        """

        return descriptor

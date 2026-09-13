"""Additive capability extension section shared by both provider projections.

Provider model schemas have no native field for most descriptor attributes. Rather
than inventing top-level fields (which would break provider client parsers), every
non-native attribute is emitted inside one documented extension object, identical
across dialects.
"""

from __future__ import annotations

from typing import Any, Final

from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor

EXTENSION_KEY: Final[str] = "x-agent-runtime"


class CapabilityExtensions:
    """Builds the additive extension object for a descriptor.

    The route key is deliberately excluded: it is an internal dispatch detail and
    publishing it would leak routing topology to every discovery caller.
    """

    @staticmethod
    def build(descriptor: AgentDescriptor) -> dict[str, Any]:
        capabilities = descriptor.capabilities
        payload: dict[str, Any] = {
            "displayName": descriptor.display_name,
            "description": descriptor.description,
            "version": descriptor.version,
            "owner": descriptor.owner,
            "tags": list(descriptor.tags),
            "capabilities": capabilities.to_dict(),
            "skills": [skill.to_dict() for skill in descriptor.skills],
            "securitySchemes": list(descriptor.security_schemes),
        }
        if descriptor.documentation_url is not None:
            payload["documentationUrl"] = descriptor.documentation_url
        if descriptor.metadata:
            payload["metadata"] = dict(descriptor.metadata)
        return payload

    @staticmethod
    def attach(target: dict[str, Any], descriptor: AgentDescriptor) -> dict[str, Any]:
        target[EXTENSION_KEY] = CapabilityExtensions.build(descriptor)
        return target

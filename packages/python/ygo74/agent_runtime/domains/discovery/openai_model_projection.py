"""OpenAI-compatible model projection.

A pure function of the descriptor: no configuration, no state. Native OpenAI model
fields are populated from descriptor identity; everything else lives in the shared
additive extension section.
"""

from __future__ import annotations

from typing import Any, Final, Sequence

from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.discovery.capability_extensions import CapabilityExtensions

MODEL_OBJECT: Final[str] = "model"
LIST_OBJECT: Final[str] = "list"


class OpenAiModelProjection:
    """Renders descriptors into the OpenAI model and model-list wire shapes."""

    @staticmethod
    def project(descriptor: AgentDescriptor) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": descriptor.agent_id,
            "object": MODEL_OBJECT,
            "created": int(descriptor.created_at_utc.timestamp()),
            "owned_by": descriptor.owner,
        }
        return CapabilityExtensions.attach(entry, descriptor)

    @staticmethod
    def project_list(descriptors: Sequence[AgentDescriptor]) -> dict[str, Any]:
        return {
            "object": LIST_OBJECT,
            "data": [OpenAiModelProjection.project(descriptor) for descriptor in descriptors],
        }

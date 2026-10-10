"""Anthropic-compatible model projection with the paginated list envelope.

A pure function of the descriptor. Shared attributes are rendered from the same
descriptor fields as the OpenAI projection, which is what makes cross-surface
consistency provable rather than incidental.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.discovery.capability_extensions import (
    CapabilityExtensions,
)
from ygo74.agent_runtime.domains.discovery.pagination import PaginationResult

MODEL_TYPE: Final[str] = "model"


class AnthropicModelProjection:
    """Renders descriptors into the Anthropic model and paginated list wire shapes."""
    @staticmethod
    def project(descriptor: AgentDescriptor) -> dict[str, Any]:
        """Project runtime data into the response shape required by the selected protocol.

        Args:
            descriptor (AgentDescriptor): The canonical agent descriptor whose identity and capabilities are used.
        """
        entry: dict[str, Any] = {
            "type": MODEL_TYPE,
            "id": descriptor.agent_id,
            "display_name": descriptor.display_name,
            "created_at": _iso_utc(descriptor),
        }
        return CapabilityExtensions.attach(entry, descriptor)

    @staticmethod
    def project_list(descriptors: Sequence[AgentDescriptor]) -> dict[str, Any]:
        """Project all entries runtime data into the provider-compatible list envelope.

        Args:
            descriptors (Sequence[AgentDescriptor]): Agent descriptors to validate, order, or register.
        """
        entries = [AnthropicModelProjection.project(descriptor) for descriptor in descriptors]
        return {
            "data": entries,
            "first_id": entries[0]["id"] if entries else None,
            "last_id": entries[-1]["id"] if entries else None,
            "has_more": False,
        }

    @staticmethod
    def project_page(page: PaginationResult[AgentDescriptor]) -> dict[str, Any]:
        """Project the selected page runtime data into the provider-compatible paginated envelope.

        Args:
            page (PaginationResult[AgentDescriptor]): Requested page size and cursor values for discovery pagination.
        """
        return {
            "data": [AnthropicModelProjection.project(descriptor) for descriptor in page.items],
            "first_id": page.first_id,
            "last_id": page.last_id,
            "has_more": page.has_more,
        }


def _iso_utc(descriptor: AgentDescriptor) -> str:
    """Format a creation timestamp in the UTC ISO-8601 form expected by Anthropic model listings.

    Args:
        descriptor (AgentDescriptor): The canonical agent descriptor whose identity and capabilities are used.
    """
    return descriptor.to_dict()["createdAtUtc"]

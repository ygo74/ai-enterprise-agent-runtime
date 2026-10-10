"""Framework-independent contract for model-backed reasoning."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel
from ygo74.agent_runtime.domains.security.prompt_envelope import (
    ReasoningRequest,
    UntrustedSection,
)

__all__ = ["ReasoningOutputT", "ReasoningRequest", "TextReasoner", "UntrustedSection"]

ReasoningOutputT = TypeVar("ReasoningOutputT", bound=BaseModel)


@runtime_checkable
class TextReasoner(Protocol):
    """Produce a validated typed result from a reasoning request."""
    async def reason(
        self,
        request: ReasoningRequest,
        response_model: type[ReasoningOutputT],
    ) -> ReasoningOutputT:
        """Return a result conforming to ``response_model``.

        Args:
            request (ReasoningRequest): The request received at this layer, with its protocol-specific or normalized fields.
            response_model (type[ReasoningOutputT]): Pydantic model used to validate structured reasoning output.
        """
        ...

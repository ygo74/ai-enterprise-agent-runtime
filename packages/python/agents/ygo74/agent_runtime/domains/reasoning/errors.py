"""Errors raised by a model-backed reasoner."""

from __future__ import annotations

from ygo74.agent_runtime.domains.errors import DomainError


class ReasoningError(DomainError):
    """Base class for language-model reasoning failures."""


class ReasoningUnavailableError(ReasoningError):
    """Raised when the reasoning backend cannot be reached."""


class ReasoningOutputError(ReasoningError):
    """Raised when a reasoner's answer cannot be used by the domain."""

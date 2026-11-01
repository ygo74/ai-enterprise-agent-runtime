"""Shared base errors raised by agent domains."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for errors with domain meaning.

    Producers may explicitly supply a credential-free diagnostic for operator
    logs. The exception message itself is not assumed safe to log.
    """

    safe_diagnostic_detail: str | None = None


class DomainValidationError(DomainError):
    """Raised when domain data violates a business invariant."""

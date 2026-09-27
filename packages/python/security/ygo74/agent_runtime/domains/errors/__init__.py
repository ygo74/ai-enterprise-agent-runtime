"""Shared base errors raised by agent domains."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for errors with domain meaning."""


class DomainValidationError(DomainError):
    """Raised when domain data violates a business invariant."""

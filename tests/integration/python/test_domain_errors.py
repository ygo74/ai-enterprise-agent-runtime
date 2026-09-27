"""Tests for the shared Python domain error types."""

from __future__ import annotations

import pytest
from ygo74.agent_runtime.domains.errors import DomainError, DomainValidationError


def test_domain_validation_error_is_a_domain_error() -> None:
    error = DomainValidationError("invalid domain value")

    assert isinstance(error, DomainError)
    assert str(error) == "invalid domain value"


def test_domain_error_can_be_caught_at_a_domain_boundary() -> None:
    with pytest.raises(DomainError, match="domain failure"):
        raise DomainError("domain failure")

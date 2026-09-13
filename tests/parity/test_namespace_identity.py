"""The Python namespace identity, across the three distributions.

The parity suite asks the same question of each language: does the library occupy
the namespace the contract says it does? For Python that question changed shape
when the runtime was split - the namespace is now contributed by three
distributions rather than owned by one - but the answer must still be yes.
"""

from __future__ import annotations

from ygo74.agent_runtime import domains
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
)
from ygo74.agent_runtime.domains.security.permissions import Permission


def test_namespace_identity_python_root() -> None:
    assert domains.__name__ == "ygo74.agent_runtime.domains"


def test_each_distribution_occupies_the_agreed_namespace() -> None:
    """One name from each side of the split, reached where the contract says."""
    assert Permission.__module__ == "ygo74.agent_runtime.domains.security.permissions"
    assert StandardExchangeRequest.__module__ == "ygo74.agent_runtime.domains.contracts.exchange_models"

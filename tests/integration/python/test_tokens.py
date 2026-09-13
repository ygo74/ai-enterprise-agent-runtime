"""Tests of the credentials that cross an agent.

Two properties, both security properties rather than conveniences. A credential
must survive careless logging, because a token in a log is a token in an incident
report. And a token obtained for one audience must be recognisable as such, so
that relaying it to another is a visible mistake rather than an invisible one.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.tokens import (
    AccessToken,
    DelegatedTokenSource,
    TokenExchangeError,
    TokenVerificationError,
    TokenVerifier,
)
from ygo74.agent_runtime.domains.security.security_errors import SecurityError

# A fabricated string that merely looks like a token, so the redaction tests can
# assert it never appears in a representation.
SECRET = "ey.this-is-a-token-value"  # noqa: S105

ADA = AgentPrincipal(subject="3f9a-user", email="ada@example.com")


def test_its_representation_hides_the_value() -> None:
    token = AccessToken(SECRET, audience="mail-mcp")

    assert SECRET not in repr(token)
    assert SECRET not in str(token)
    assert SECRET not in f"token={token}"


def test_the_representation_still_identifies_the_audience() -> None:
    """Redaction must not make an operator blind to what failed."""
    assert "mail-mcp" in repr(AccessToken(SECRET, audience="mail-mcp"))


def test_the_representation_reports_the_length_rather_than_the_value() -> None:
    assert f"length={len(SECRET)}" in repr(AccessToken(SECRET))


def test_the_value_is_reachable_only_through_an_explicit_call() -> None:
    """`expose` is what makes every dereference of a credential greppable."""
    assert AccessToken(SECRET).expose() == SECRET


def test_an_empty_credential_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        AccessToken("")


def test_a_credential_cannot_be_mutated_after_it_is_issued() -> None:
    token = AccessToken(SECRET, audience="mail-mcp")

    with pytest.raises(AttributeError):
        token.audience = "somewhere-else"  # type: ignore[misc]


def test_token_failures_are_security_failures() -> None:
    """One `except SecurityError` catches the whole security model."""
    assert issubclass(TokenVerificationError, SecurityError)
    assert issubclass(TokenExchangeError, SecurityError)


class _Verifier:
    """A verifier that trusts exactly one credential."""

    def verify(self, token: AccessToken) -> AgentPrincipal:
        if token.expose() != SECRET:
            raise TokenVerificationError("the presented token cannot be trusted")
        return ADA


class _Exchange:
    """A delegated source that mints one token per audience."""

    async def token_for(self, principal: AgentPrincipal, audience: str) -> AccessToken:
        if not audience:
            raise TokenExchangeError("an exchange needs an audience")
        return AccessToken(f"minted-for-{principal.subject}", audience=audience)


class _NotAVerifier:
    """Structurally close, but missing the one method the port requires."""

    def check(self, token: AccessToken) -> AgentPrincipal:
        del token
        return ADA


def test_the_ports_accept_a_conforming_implementation() -> None:
    assert isinstance(_Verifier(), TokenVerifier)
    assert isinstance(_Exchange(), DelegatedTokenSource)


def test_the_ports_reject_an_implementation_that_does_not_conform() -> None:
    """A protocol that accepted anything would document nothing."""
    assert not isinstance(_NotAVerifier(), TokenVerifier)
    assert not isinstance(_Verifier(), DelegatedTokenSource)


def test_a_verifier_hands_back_an_identity_carrying_no_credential() -> None:
    """Rule three: verification produces a principal and nothing else.

    Exercised through the port so the signature is the thing under test - an
    implementation returning a token, or a dict of claims, would not type-check
    against it.
    """
    verifier: TokenVerifier = _Verifier()

    principal = verifier.verify(AccessToken(SECRET))

    assert principal == ADA
    assert SECRET not in repr(principal)


def test_a_delegated_source_mints_a_token_for_the_next_hop() -> None:
    """Rule two: the agent exchanges a token instead of relaying one.

    The MCP specification forbids passthrough and requires a server to check that
    a token was issued for it, which it cannot do if the agent forwards the one
    its own caller presented. The port's signature is what enforces the shape:
    it takes a principal and an audience, never an inbound token.
    """
    source: DelegatedTokenSource = _Exchange()

    minted = asyncio.run(source.token_for(ADA, "mail-mcp"))

    assert minted.audience == "mail-mcp"
    assert minted.expose() != SECRET


def test_the_exchange_port_cannot_be_handed_an_inbound_token() -> None:
    """The signature is the control: there is no parameter to relay one through."""
    parameters = inspect.signature(DelegatedTokenSource.token_for).parameters

    assert list(parameters) == ["self", "principal", "audience"]

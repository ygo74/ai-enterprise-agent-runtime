"""Contracts for provider supplied OAuth token delegation."""

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.tokens import AccessToken, DelegatedTokenRequest


def test_delegated_token_request_keeps_the_subject_token_redacted() -> None:
    """A host receives a typed exchange request with audience and pinned scopes."""
    subject_token = AccessToken("incoming-secret", audience="agent-api")
    request = DelegatedTokenRequest(
        principal=AgentPrincipal(subject="user-42"),
        subject_token=subject_token,
        audience="https://mcp.example.test",
        scopes=("mail.read", "mail.send"),
    )

    assert request.principal.subject == "user-42"
    assert request.subject_token is subject_token
    assert request.audience == "https://mcp.example.test"
    assert request.scopes == ("mail.read", "mail.send")
    assert "incoming-secret" not in repr(request)

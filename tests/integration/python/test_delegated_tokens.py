"""Contracts for provider supplied OAuth token delegation."""

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.tokens import (
    AccessToken,
    DelegatedTokenRequest,
    OAuthOnBehalfOfTokenSource,
)


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


def test_on_behalf_of_source_is_a_separate_provider_contract() -> None:
    """The OBO port accepts exchange input without changing the credential-free port."""

    class FakeOAuthOnBehalfOfSource:
        """Return an audience-bound token for the request's verified principal."""

        async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
            return AccessToken("downstream-token", audience=request.audience)

    assert isinstance(FakeOAuthOnBehalfOfSource(), OAuthOnBehalfOfTokenSource)

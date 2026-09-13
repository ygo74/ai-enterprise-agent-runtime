"""Tests of reading an MCP server's authentication from the environment.

The schemes are tested in `test_authentication_policy.py`; the guard in
`test_mcp_server_hosting.py`. What is tested here is only the mapping - and one
property of it that matters more than the rest.

A server hosting MCP tools holds a credential for whatever is behind them. Adding a
`none` mode is precisely the change that can turn a forgotten environment variable
into an open port, so the first class below checks that it did not.
"""

from __future__ import annotations

import time

import pytest

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.authentication_policy import (
    AuthenticationConfigurationError,
    AuthenticationMode,
)
from ygo74.agent_runtime.domains.mcpserver.settings import McpServerAuthentication

PREFIX = "MAIL_MCP_"
SECRET = "a-shared-deployment-secret"  # noqa: S105 - a fixture, not a credential
CALLER = "mail-agent"


def _read(**variables: str) -> McpServerAuthentication:
    return McpServerAuthentication.from_env(PREFIX, caller_id=CALLER, environment=variables)


class TestSilenceIsNotConsent:
    """The property this module exists for."""

    def test_a_server_told_nothing_refuses_to_serve(self):
        with pytest.raises(AuthenticationConfigurationError):
            _read()

    def test_the_refusal_names_the_variable_and_every_way_out(self):
        with pytest.raises(AuthenticationConfigurationError) as refusal:
            _read()

        message = str(refusal.value)
        assert f"{PREFIX}AUTH_MODE" in message
        assert "api_key" in message
        assert "jwt" in message
        assert "none" in message

    def test_anonymous_has_to_be_written_down(self):
        authentication = _read(MAIL_MCP_AUTH_MODE="none")

        assert authentication.policy.mode is AuthenticationMode.NONE
        assert not authentication.policy.requires_authentication

    @pytest.mark.parametrize("value", ["", "   "])
    def test_a_blank_mode_is_not_a_mode(self, value):
        with pytest.raises(AuthenticationConfigurationError):
            _read(MAIL_MCP_AUTH_MODE=value)


class TestTheSchemeMayBeInferred:
    """A deployment that set a token has said something unambiguous.

    Breaking every running container to make it say the same thing twice would buy
    nothing. Inferring *anonymity* would buy a security incident, and that is the
    distinction the inference respects.
    """

    def test_a_configured_token_means_the_token_is_checked(self):
        assert _read(MAIL_MCP_HTTP_TOKEN=SECRET).policy.mode is AuthenticationMode.API_KEY

    def test_a_configured_issuer_means_tokens_are_validated(self):
        authentication = _read(
            MAIL_MCP_OIDC_ISSUER="https://idp.example/realms/agents",
            MAIL_MCP_RESOURCE_URL="https://mail-mcp.example",
        )

        assert authentication.policy.mode is AuthenticationMode.JWT

    def test_an_explicit_mode_wins_over_what_is_lying_around(self):
        """A leftover token must not quietly re-enable a scheme somebody turned off."""
        authentication = _read(MAIL_MCP_AUTH_MODE="none", MAIL_MCP_HTTP_TOKEN=SECRET)

        assert authentication.policy.mode is AuthenticationMode.NONE


class TestTheSharedSecret:
    """What a container deployment actually runs."""

    def _chain(self):
        return _read(MAIL_MCP_AUTH_MODE="api_key", MAIL_MCP_HTTP_TOKEN=SECRET).policy.build()

    def test_it_is_read_from_an_authorization_header(self):
        context = self._chain().authenticate({"authorization": f"Bearer {SECRET}"})

        assert context is not None
        assert context.identity.user_id == CALLER

    def test_a_wrong_secret_is_refused(self):
        with pytest.raises(AuthenticationError):
            self._chain().authenticate({"authorization": "Bearer not-the-secret"})

    def test_a_prefix_of_the_secret_is_refused(self):
        with pytest.raises(AuthenticationError):
            self._chain().authenticate({"authorization": f"Bearer {SECRET[:-1]}"})

    def test_the_mode_without_a_secret_is_refused_at_start_up(self):
        with pytest.raises(AuthenticationConfigurationError, match=f"{PREFIX}HTTP_TOKEN"):
            _read(MAIL_MCP_AUTH_MODE="api_key")

    def test_the_identity_is_a_deployment_not_a_person(self):
        """The secret proves which caller, never whose data.

        Whose data was settled by the credential the server itself holds, and an
        identity suggesting otherwise would be a claim it cannot back.
        """
        context = self._chain().authenticate({"authorization": f"Bearer {SECRET}"})

        assert context is not None
        assert context.identity.user_id == CALLER


class TestTheOidcDeployment:
    """A server behind a realm, discoverable by a generic MCP client."""

    def test_it_carries_the_resource_it_names_itself_by(self):
        authentication = _read(
            MAIL_MCP_AUTH_MODE="jwt",
            MAIL_MCP_OIDC_ISSUER="https://idp.example/realms/agents",
            MAIL_MCP_RESOURCE_URL="https://mail-mcp.example",
        )

        assert authentication.resource_url == "https://mail-mcp.example"

    def test_it_is_refused_without_an_issuer(self):
        with pytest.raises(AuthenticationConfigurationError, match=f"{PREFIX}OIDC_ISSUER"):
            _read(MAIL_MCP_AUTH_MODE="jwt")

    def test_it_is_refused_without_a_resource_url(self):
        with pytest.raises(AuthenticationConfigurationError, match=f"{PREFIX}RESOURCE_URL"):
            _read(MAIL_MCP_AUTH_MODE="jwt", MAIL_MCP_OIDC_ISSUER="https://idp.example/realms/agents")

    def test_no_symmetric_algorithm_is_accepted(self):
        """HS256 would mean the server holds the key that signs tokens.

        That turns a resource server into an issuer by accident, and anyone who can
        read the server's configuration can then mint tokens for it.
        """
        authentication = _read(
            MAIL_MCP_AUTH_MODE="jwt",
            MAIL_MCP_OIDC_ISSUER="https://idp.example/realms/agents",
            MAIL_MCP_RESOURCE_URL="https://mail-mcp.example",
        )
        allowed = authentication.policy.authenticators[0].config.allowed_algorithms

        assert not [name for name in allowed if name.startswith("HS")]


class TestJwtModeCanActuallyAuthenticate:
    """The test that was missing, and the defect it would have caught.

    Asserting the mode and the config shape says nothing about whether a token gets
    in. Without a signing-key resolver the authenticator refuses every token before
    it reaches a signature check - so the server publishes discovery metadata, sends
    a client to the right realm, and answers 401 to the valid token it comes back
    with. It fails closed, which is exactly why only driving a real token finds it.
    """

    ISSUER = "https://idp.example/realms/agents"
    AUDIENCE = "mail-mcp"

    @staticmethod
    def _signing_key():
        from cryptography.hazmat.primitives.asymmetric import rsa

        return rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def _policy(self, key, **extra: str):
        """A policy whose key resolver returns the local key, never a network one."""
        authentication = _read(
            MAIL_MCP_AUTH_MODE="jwt",
            MAIL_MCP_OIDC_ISSUER=self.ISSUER,
            MAIL_MCP_OIDC_AUDIENCE=self.AUDIENCE,
            MAIL_MCP_RESOURCE_URL="https://mail-mcp.example",
            **extra,
        )
        config = authentication.policy.authenticators[0].config
        config.key_resolver = _LocalKeyResolver(key.public_key())
        return authentication.policy

    def _token(self, key, **claims: object) -> str:
        import jwt

        payload: dict[str, object] = {
            "sub": "alice",
            "iss": self.ISSUER,
            "aud": self.AUDIENCE,
            "exp": int(time.time()) + 600,
        }
        payload.update(claims)
        return jwt.encode(payload, key, algorithm="RS256")

    def test_a_resolver_is_configured_at_all(self):
        """The direct shape of the defect: no resolver, no possible caller."""
        authentication = _read(
            MAIL_MCP_AUTH_MODE="jwt",
            MAIL_MCP_OIDC_ISSUER=self.ISSUER,
            MAIL_MCP_RESOURCE_URL="https://mail-mcp.example",
        )

        assert authentication.policy.authenticators[0].config.key_resolver is not None

    def test_reading_the_configuration_reaches_no_network(self):
        """A server must not fail to start because its issuer is briefly down.

        The key set is discovered on the first token, which is when it is fetched
        anyway. A resolver that discovered eagerly would also make this test need a
        network.
        """
        authentication = _read(
            MAIL_MCP_AUTH_MODE="jwt",
            MAIL_MCP_OIDC_ISSUER="https://unreachable.invalid/realms/x",
            MAIL_MCP_RESOURCE_URL="https://mail-mcp.example",
        )

        assert authentication.policy.mode is AuthenticationMode.JWT

    def test_an_explicit_key_set_url_wins_over_discovery(self):
        from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwksKeyResolver

        authentication = _read(
            MAIL_MCP_AUTH_MODE="jwt",
            MAIL_MCP_OIDC_ISSUER=self.ISSUER,
            MAIL_MCP_RESOURCE_URL="https://mail-mcp.example",
            MAIL_MCP_JWKS_URL="https://idp.example/keys",
        )
        resolver = authentication.policy.authenticators[0].config.key_resolver

        assert isinstance(resolver, JwksKeyResolver)
        assert resolver.jwks_url == "https://idp.example/keys"

    def test_a_valid_token_is_accepted(self):
        key = self._signing_key()

        context = self._policy(key).build().authenticate(
            {"authorization": f"Bearer {self._token(key)}"}
        )

        assert context is not None
        assert context.identity.user_id == "alice"

    def test_a_token_from_another_issuer_is_refused(self):
        key = self._signing_key()

        with pytest.raises(AuthenticationError):
            self._policy(key).build().authenticate(
                {"authorization": f"Bearer {self._token(key, iss='https://attacker.example')}"}
            )

    def test_a_token_for_another_audience_is_refused(self):
        key = self._signing_key()

        with pytest.raises(AuthenticationError):
            self._policy(key).build().authenticate(
                {"authorization": f"Bearer {self._token(key, aud='some-other-service')}"}
            )

    def test_an_expired_token_is_refused(self):
        key = self._signing_key()

        with pytest.raises(AuthenticationError):
            self._policy(key).build().authenticate(
                {"authorization": f"Bearer {self._token(key, exp=int(time.time()) - 60)}"}
            )

    def test_a_token_signed_by_somebody_else_is_refused(self):
        key = self._signing_key()
        impostor = self._signing_key()

        with pytest.raises(AuthenticationError):
            self._policy(key).build().authenticate(
                {"authorization": f"Bearer {self._token(impostor)}"}
            )


class _LocalKeyResolver:
    """Returns one key, so a test needs no network and no key set server."""

    def __init__(self, public_key: object) -> None:
        self._public_key = public_key

    def resolve_key(self, token: str, unverified_header: dict[str, object]) -> object:
        return self._public_key


class TestTwoServersInOneDeployment:
    """The prefix is what keeps them apart - and what keeps them the same.

    Two servers reading the same variables would authenticate each other's callers.
    Two servers with their own *logic* would drift until one was weaker. The prefix
    gives the first without the second.
    """

    def test_each_prefix_reads_its_own_variables(self):
        environment = {
            "MAIL_MCP_AUTH_MODE": "api_key",
            "MAIL_MCP_HTTP_TOKEN": "mail-secret",
            "WIKI_MCP_AUTH_MODE": "none",
        }

        mail = McpServerAuthentication.from_env("MAIL_MCP_", caller_id="mail", environment=environment)
        wiki = McpServerAuthentication.from_env("WIKI_MCP_", caller_id="wiki", environment=environment)

        assert mail.policy.mode is AuthenticationMode.API_KEY
        assert wiki.policy.mode is AuthenticationMode.NONE

    def test_one_server_s_secret_does_not_open_the_other(self):
        environment = {
            "MAIL_MCP_AUTH_MODE": "api_key",
            "MAIL_MCP_HTTP_TOKEN": "mail-secret",
            "WIKI_MCP_AUTH_MODE": "api_key",
            "WIKI_MCP_HTTP_TOKEN": "wiki-secret",
        }

        wiki = McpServerAuthentication.from_env("WIKI_MCP_", caller_id="wiki", environment=environment)

        with pytest.raises(AuthenticationError):
            wiki.policy.build().authenticate({"authorization": "Bearer mail-secret"})

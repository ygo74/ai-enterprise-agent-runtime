"""Tests of the authentication policy: which schemes a host accepts, and why.

The runtime already had the schemes - an API key with a pluggable user resolver, a
JWT validated against an OIDC issuer, and an `Authenticator` protocol for anything
else. What it did not have was a way to *say* which of them a host accepts, so a
host said it by which keyword arguments it happened to pass.

That worked while agents were the only host. It stops working the moment an MCP
server shares the model, because an MCP server may legitimately be anonymous - and
"anonymous" and "nobody configured authentication" must never be the same state.

The first class of test below is the one that matters. Everything else here is
plumbing; that one is the security property.
"""

from __future__ import annotations

import pytest

from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    ApiKeyAuthenticator,
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import AuthenticatedUserContext, ResolvedUser
from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.authentication_policy import (
    AuthenticationConfigurationError,
    AuthenticationMode,
    AuthenticationPolicy,
)
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtValidationConfig

SECRET = "a-shared-deployment-secret"  # noqa: S105 - a fixture, not a credential


def _resolver() -> StaticApiKeyUserResolver:
    return StaticApiKeyUserResolver(
        {SECRET: ResolvedUser(user_id="svc-mail-agent", name="Mail Agent", roles=["agent"])}
    )


class TestAnonymousIsNeverAnAccident:
    """The property this module exists for.

    A host that forgot to configure authentication and a host that deliberately
    serves everyone must not reach the same state. One is a mistake that should
    stop the process; the other is a decision somebody made and can be asked
    about.
    """

    def test_a_policy_built_from_nothing_is_refused(self):
        with pytest.raises(AuthenticationConfigurationError, match="no authentication scheme"):
            AuthenticationPolicy.of()

    def test_anonymous_must_be_asked_for_by_name(self):
        policy = AuthenticationPolicy.anonymous()

        assert policy.mode is AuthenticationMode.NONE
        assert not policy.requires_authentication

    def test_an_anonymous_policy_says_so_when_asked(self):
        """A host logs this at start-up, so it must not be silent."""
        assert "anonymous" in AuthenticationPolicy.anonymous().describe().lower()

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_an_unset_mode_is_not_anonymous(self, value):
        with pytest.raises(AuthenticationConfigurationError, match="no authentication mode"):
            AuthenticationMode.named(value)

    def test_an_unknown_mode_names_the_ones_that_exist(self):
        with pytest.raises(AuthenticationConfigurationError) as refusal:
            AuthenticationMode.named("kerberos")

        assert "kerberos" in str(refusal.value)
        assert "api_key" in str(refusal.value)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("none", AuthenticationMode.NONE),
            ("api_key", AuthenticationMode.API_KEY),
            ("JWT", AuthenticationMode.JWT),
            ("  api_key  ", AuthenticationMode.API_KEY),
        ],
    )
    def test_a_named_mode_is_read_forgivingly(self, value, expected):
        assert AuthenticationMode.named(value) is expected


class TestAPolicyBuildsTheChain:
    """What a host actually gets."""

    def test_an_api_key_policy_accepts_the_configured_key(self):
        chain = AuthenticationPolicy.api_key(_resolver()).build()

        context = chain.authenticate({"x-api-key": SECRET})

        assert isinstance(context, AuthenticatedUserContext)
        assert context.identity.user_id == "svc-mail-agent"

    def test_an_api_key_policy_refuses_an_unknown_key(self):
        chain = AuthenticationPolicy.api_key(_resolver()).build()

        with pytest.raises(AuthenticationError) as refusal:
            chain.authenticate({"x-api-key": "not-the-secret"})

        assert refusal.value.code == "api_key_invalid"

    def test_an_api_key_policy_requires_a_credential(self):
        chain = AuthenticationPolicy.api_key(_resolver()).build()

        with pytest.raises(AuthenticationError):
            chain.authenticate({})

    def test_an_anonymous_policy_lets_a_bare_request_through(self):
        chain = AuthenticationPolicy.anonymous().build()

        assert chain.authenticate({}) is None

    def test_jwt_is_evaluated_before_an_api_key(self):
        """Precedence, not accident: an Authorization header always wins.

        Both authenticators claim different headers, so the order only shows when a
        request carries both - which is exactly when a caller must not be able to
        pick the weaker scheme.
        """
        policy = AuthenticationPolicy.of(
            *AuthenticationPolicy.jwt(JwtValidationConfig(issuer="https://idp.example")).authenticators,
            *AuthenticationPolicy.api_key(_resolver()).authenticators,
        )

        assert [a.auth_type for a in policy.build().authenticators] == ["jwt", "api_key"]


class TestASchemePrefixedApiKey:
    """`Authorization: Bearer <secret>` is an API key wearing a scheme.

    The deployed mail MCP server presents its shared secret that way, so a policy
    that could only read a bare header value would have broken a running
    deployment on the day it adopted this model.
    """

    def _chain(self):
        return AuthenticationPolicy.api_key(
            _resolver(), header_name="authorization", scheme="Bearer"
        ).build()

    def test_the_scheme_is_stripped_before_the_key_is_resolved(self):
        context = self._chain().authenticate({"authorization": f"Bearer {SECRET}"})

        assert context is not None
        assert context.identity.user_id == "svc-mail-agent"

    def test_the_scheme_is_matched_whatever_its_case(self):
        assert self._chain().authenticate({"authorization": f"bearer {SECRET}"}) is not None

    def test_a_header_carrying_another_scheme_is_not_claimed(self):
        """It must not swallow a credential meant for a different authenticator."""
        authenticator = ApiKeyAuthenticator(_resolver(), header_name="authorization", scheme="Bearer")

        assert not authenticator.can_authenticate({"authorization": f"Basic {SECRET}"})

    def test_a_bare_value_is_refused_when_a_scheme_was_required(self):
        authenticator = ApiKeyAuthenticator(_resolver(), header_name="authorization", scheme="Bearer")

        assert not authenticator.can_authenticate({"authorization": SECRET})

    def test_without_a_scheme_the_raw_value_is_still_the_key(self):
        """The default behaviour, unchanged."""
        chain = AuthenticationPolicy.api_key(_resolver()).build()

        assert chain.authenticate({"x-api-key": SECRET}) is not None


class TestTheExtensionPoint:
    """Adding a scheme must not mean editing the foundation.

    Basic here stands in for Kerberos, mutual TLS, or whatever a deployment
    actually has. If this test needs a change to `AuthenticationPolicy` to pass,
    the extension point is not one.
    """

    class BasicAuthenticator:
        """A third-party scheme, written entirely outside the runtime."""

        def __init__(self, users: dict[str, str]) -> None:
            self._users = users

        @property
        def auth_type(self) -> str:
            return "basic"

        @property
        def header_name(self) -> str:
            return "authorization"

        def can_authenticate(self, headers):
            header = headers.get("authorization", "")
            return isinstance(header, str) and header.lower().startswith("basic ")

        def missing_credential_error(self) -> AuthenticationError:
            return AuthenticationError(code="basic_credential_missing", message="Missing Basic credential")

        def authenticate(self, headers) -> AuthenticatedUserContext:
            import base64

            raw = headers["authorization"].split(None, 1)[1]
            user, _, password = base64.b64decode(raw).decode().partition(":")
            if self._users.get(user) != password:
                raise AuthenticationError(code="basic_invalid", message="Unknown user or password")
            return AuthenticatedUserContext(
                auth_type=self.auth_type,
                identity=ResolvedUser(user_id=user).to_identity(),
            )

    def _header(self, user: str, password: str) -> dict[str, str]:
        import base64

        encoded = base64.b64encode(f"{user}:{password}".encode()).decode()
        return {"authorization": f"Basic {encoded}"}

    def test_a_scheme_the_runtime_never_heard_of_can_be_used(self):
        policy = AuthenticationPolicy.of(self.BasicAuthenticator({"alice": "correct"}))

        context = policy.build().authenticate(self._header("alice", "correct"))

        assert context is not None
        assert context.identity.user_id == "alice"
        assert context.auth_type == "basic"

    def test_such_a_policy_still_requires_a_credential(self):
        policy = AuthenticationPolicy.of(self.BasicAuthenticator({"alice": "correct"}))

        assert policy.requires_authentication
        with pytest.raises(AuthenticationError):
            policy.build().authenticate({})

    def test_it_reports_the_mode_as_the_scheme_it_was_given(self):
        policy = AuthenticationPolicy.of(self.BasicAuthenticator({}))

        assert policy.mode is AuthenticationMode.CUSTOM
        assert "basic" in policy.describe()

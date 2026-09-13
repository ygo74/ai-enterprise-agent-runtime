"""Reading an MCP server's authentication out of the environment.

The schemes live in :mod:`ygo74.agent_runtime.domains.auth`; this is only the
mapping from environment variables onto them. It sits in the library rather than in
each server because two servers in one deployment growing two different answers to
"who may call me" is how a weaker one appears without anybody deciding it should.

The prefix is what distinguishes them - ``MAIL_MCP_``, ``WIKI_MCP_`` - exactly as
``AgentHttpSettings.from_env`` distinguishes two agents in one process.

Variables, for a prefix of ``MAIL_MCP_``:

``MAIL_MCP_AUTH_MODE``
    ``none``, ``api_key`` or ``jwt``.
``MAIL_MCP_HTTP_TOKEN``
    The shared secret, for ``api_key``.
``MAIL_MCP_OIDC_ISSUER`` and ``MAIL_MCP_OIDC_AUDIENCE``
    The issuer to validate against, for ``jwt``.
``MAIL_MCP_RESOURCE_URL``
    What the server calls itself as an OAuth resource, required for ``jwt``.

**The mode may be inferred, but never inferred as anonymous.** A deployment that set
a token has said something unambiguous, and breaking every running container to make
it say the same thing twice would buy nothing. A deployment that set nothing has said
nothing, and gets a refusal rather than an open port.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Self

from ygo74.agent_runtime.domains.auth.apikey_authenticator import StaticApiKeyUserResolver
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import (
    AuthenticationConfigurationError,
    AuthenticationMode,
    AuthenticationPolicy,
)
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtValidationConfig

MODE_SUFFIX = "AUTH_MODE"
TOKEN_SUFFIX = "HTTP_TOKEN"  # noqa: S105 - the name of a variable, not its value
ISSUER_SUFFIX = "OIDC_ISSUER"
AUDIENCE_SUFFIX = "OIDC_AUDIENCE"
RESOURCE_SUFFIX = "RESOURCE_URL"

# Symmetric algorithms are refused: HS256 would mean the server holds the same key
# that signs tokens, which turns a resource server into an issuer by accident.
ASYMMETRIC_ALGORITHMS = ("RS256", "RS384", "RS512", "ES256", "ES384")


@dataclass(frozen=True, slots=True)
class McpServerAuthentication:
    """The authentication an MCP server was configured with."""

    policy: AuthenticationPolicy
    resource_url: str = ""

    @classmethod
    def from_env(
        cls,
        prefix: str,
        *,
        caller_id: str,
        environment: dict[str, str] | None = None,
    ) -> Self:
        """Read one server's authentication from prefixed environment variables.

        Args:
            prefix: What distinguishes this server's variables - ``MAIL_MCP_``.
            caller_id: Who the shared secret authenticates, in ``api_key`` mode. A
                deployment, not a person: the secret says "you are the agent I was
                deployed with" and nothing about whose data is read.
            environment: Read instead of the process environment, for tests.

        Raises:
            AuthenticationConfigurationError: nothing was configured, or what was
                configured is incomplete. Always fatal: a server that started anyway
                would be its tools on an open port, and the only sign of it would be
                the absence of a line in a log.
        """
        source = environment if environment is not None else dict(os.environ)
        names = _Names(prefix)
        mode = cls._mode(source, names)

        if mode is AuthenticationMode.NONE:
            return cls(AuthenticationPolicy.anonymous())

        if mode is AuthenticationMode.API_KEY:
            return cls(cls._api_key_policy(source, names, caller_id))

        return cls(cls._jwt_policy(source, names), _required(source, names.resource, names.mode, "jwt"))

    @staticmethod
    def _mode(source: dict[str, str], names: _Names) -> AuthenticationMode:
        """Which mode was asked for, inferring a scheme but never inferring silence."""
        declared = source.get(names.mode, "").strip()
        if declared:
            return AuthenticationMode.named(declared)

        if source.get(names.token, "").strip():
            # Unambiguous: a token was configured, so a token is what is checked.
            return AuthenticationMode.API_KEY

        if source.get(names.issuer, "").strip():
            return AuthenticationMode.JWT

        raise AuthenticationConfigurationError(
            f"serving over HTTP requires {names.mode}: this process holds a credential for the "
            "system behind it, and an unauthenticated port would hand that system to anything "
            f"that can reach it. Set {names.mode}=api_key with {names.token}, or {names.mode}=jwt "
            f"with {names.issuer}, or {names.mode}=none if serving everyone really is the intent"
        )

    @staticmethod
    def _api_key_policy(source: dict[str, str], names: _Names, caller_id: str) -> AuthenticationPolicy:
        """Authenticate a shared secret carried in an Authorization header."""
        secret = source.get(names.token, "").strip()
        if not secret:
            raise AuthenticationConfigurationError(
                f"{names.mode} is 'api_key' but {names.token} is empty: "
                "there is nothing to check a caller against"
            )

        return AuthenticationPolicy.api_key(
            StaticApiKeyUserResolver({secret: ResolvedUser(user_id=caller_id)}),
            header_name="authorization",
            scheme="Bearer",
        )

    @staticmethod
    def _jwt_policy(source: dict[str, str], names: _Names) -> AuthenticationPolicy:
        """Validate tokens against the configured issuer."""
        issuer = _required(source, names.issuer, names.mode, "jwt")
        audience = source.get(names.audience, "").strip()
        return AuthenticationPolicy.jwt(
            JwtValidationConfig(
                issuer=issuer,
                audience=audience or None,
                allowed_algorithms=ASYMMETRIC_ALGORITHMS,
            )
        )


@dataclass(frozen=True, slots=True)
class _Names:
    """The variable names of one prefix."""

    prefix: str

    @property
    def mode(self) -> str:
        return f"{self.prefix}{MODE_SUFFIX}"

    @property
    def token(self) -> str:
        return f"{self.prefix}{TOKEN_SUFFIX}"

    @property
    def issuer(self) -> str:
        return f"{self.prefix}{ISSUER_SUFFIX}"

    @property
    def audience(self) -> str:
        return f"{self.prefix}{AUDIENCE_SUFFIX}"

    @property
    def resource(self) -> str:
        return f"{self.prefix}{RESOURCE_SUFFIX}"


def _required(source: dict[str, str], variable: str, mode_variable: str, mode: str) -> str:
    """Read a variable the chosen mode cannot work without."""
    value = source.get(variable, "").strip()
    if not value:
        raise AuthenticationConfigurationError(
            f"{mode_variable} is {mode!r} but {variable} is empty: "
            "a resource server that cannot name itself or its issuer cannot be discovered"
        )
    return value

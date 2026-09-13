"""Which authentication schemes a host accepts, said out loud.

The schemes themselves already existed: an API key with a user resolver the host
writes, a JWT validated against an OIDC issuer, and the :class:`Authenticator`
protocol for anything a deployment actually has - Basic, Kerberos, mutual TLS. What
was missing was a way to *declare* which of them a host accepts. A host declared it
by which keyword arguments it happened to pass, and the absence of all of them meant
"no authentication".

That was survivable while agents were the only host, because an agent always needs
a subject: without one there is nothing to partition conversation state by. It stops
being survivable the moment an MCP server shares the model, because an MCP server
over read-only public data may legitimately serve everyone.

So anonymity becomes a decision rather than a residue. :meth:`AuthenticationPolicy.anonymous`
is the only way to reach it, :meth:`AuthenticationPolicy.of` refuses to build a
policy out of nothing, and :meth:`AuthenticationMode.named` refuses an unset value.
A deployment that forgot to configure authentication stops; a deployment that chose
to serve everyone says so, and can be asked about it later.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    ApiKeyAuthenticator,
    ApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.authenticator import Authenticator, RequestAuthenticator
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtAuthenticator, JwtValidationConfig


class AuthenticationConfigurationError(RuntimeError):
    """Raised when a host cannot be served safely as configured.

    Deliberately fatal, and deliberately not an :class:`AuthenticationError`: this
    is not a caller failing to authenticate, it is a deployment that never said how
    callers would be authenticated at all. Answering a request would mean guessing.
    """


class AuthenticationMode(StrEnum):
    """The schemes a host can be configured with.

    ``CUSTOM`` is not something a configuration file names. It is what a policy
    reports when a host supplied its own :class:`Authenticator`, so that a start-up
    log still says something true about a scheme this enumeration never heard of.
    """

    NONE = "none"
    API_KEY = "api_key"
    JWT = "jwt"
    CUSTOM = "custom"

    @classmethod
    def named(cls, value: str | None) -> AuthenticationMode:
        """Read a mode a deployment asked for, refusing silence.

        An unset value is the case this method exists for. Defaulting it to
        ``NONE`` would turn a forgotten environment variable into an open door, and
        the only sign of it would be the absence of a line in a log.

        ``CUSTOM`` is refused too. It is what a policy *reports* when a host supplied
        its own authenticator in code; naming it in a configuration file asks for a
        scheme nothing can build.
        """
        text = (value or "").strip().lower()
        known = ", ".join(mode.value for mode in cls if mode is not cls.CUSTOM)

        if not text:
            raise AuthenticationConfigurationError(
                f"no authentication mode was configured: name one of {known}. "
                "Serving without authentication is a decision, so it has to be written down as 'none'"
            )

        if text == cls.CUSTOM.value:
            raise AuthenticationConfigurationError(
                f"authentication mode 'custom' cannot be configured: it is what a policy reports "
                f"when a host passes its own authenticator to AuthenticationPolicy.of(). "
                f"Expected one of {known}"
            )

        try:
            return cls(text)
        except ValueError as error:
            raise AuthenticationConfigurationError(
                f"unknown authentication mode {text!r}: expected one of {known}"
            ) from error


class AuthenticationPolicy:
    """The schemes a host accepts, and whether a credential is required.

    Built through a named constructor rather than a keyword-argument soup, so that
    reading the composition root tells you the security posture of the service
    without having to work out what an omitted argument meant.
    """

    def __init__(self, mode: AuthenticationMode, authenticators: tuple[Authenticator, ...]) -> None:
        self._mode = mode
        self._authenticators = authenticators

    @property
    def mode(self) -> AuthenticationMode:
        """Which scheme family this policy was built for."""
        return self._mode

    @property
    def authenticators(self) -> tuple[Authenticator, ...]:
        """The schemes, in the order they are tried."""
        return self._authenticators

    @property
    def requires_authentication(self) -> bool:
        """Whether a request without a credential is refused."""
        return self._mode is not AuthenticationMode.NONE

    @classmethod
    def anonymous(cls) -> Self:
        """Serve everyone, deliberately.

        Legitimate for a server exposing public, read-only data. Not legitimate as
        the consequence of an unset variable, which is why it has a name.
        """
        return cls(AuthenticationMode.NONE, ())

    @classmethod
    def api_key(
        cls,
        resolver: ApiKeyUserResolver,
        *,
        header_name: str = ApiKeyAuthenticator.DEFAULT_HEADER_NAME,
        scheme: str = "",
    ) -> Self:
        """Authenticate a key, and let the host decide who that key is.

        ``scheme`` covers the deployments that carry their key in an
        ``Authorization`` header - the mail MCP server presents its shared secret
        as ``Bearer <secret>``. Leave it empty and the raw header value is the key.
        """
        return cls(
            AuthenticationMode.API_KEY,
            (ApiKeyAuthenticator(resolver, header_name=header_name, scheme=scheme),),
        )

    @classmethod
    def jwt(cls, validation: JwtValidationConfig) -> Self:
        """Validate a bearer token against an issuer's published keys."""
        return cls(AuthenticationMode.JWT, (JwtAuthenticator(validation),))

    @classmethod
    def of(cls, *authenticators: Authenticator) -> Self:
        """Accept schemes the host supplies itself.

        The extension point. Basic, Kerberos or mutual TLS are implementations of
        :class:`Authenticator` written outside this package; none of them requires a
        change here.

        Order is precedence: the first authenticator claiming a request wins.
        """
        if not authenticators:
            raise AuthenticationConfigurationError(
                "no authentication scheme was supplied: pass at least one authenticator, "
                "or say AuthenticationPolicy.anonymous() if serving everyone is the intent"
            )
        return cls(AuthenticationMode.CUSTOM, tuple(authenticators))

    def build(self) -> RequestAuthenticator:
        """Assemble the chain a transport runs against every request."""
        return RequestAuthenticator(
            list(self._authenticators),
            require_authentication=self.requires_authentication,
        )

    def describe(self) -> str:
        """One line for a start-up log, naming the posture rather than implying it."""
        if self._mode is AuthenticationMode.NONE:
            return "anonymous: every caller is served, no credential is checked"

        schemes = ", ".join(authenticator.auth_type for authenticator in self._authenticators)
        return f"authenticated: {schemes}"

"""How an agent is served over HTTP.

Routing and posture only. No credential is read, held or logged here: a
demonstration key is compared, never stored anywhere it could be printed, and
tokens are validated against a published key set.

Two things are deliberate.

The settings are a plain ``pydantic`` model with an explicit
:meth:`AgentHttpSettings.from_env` rather than a ``pydantic-settings`` class.
Reading configuration is a host's business, and a library that imposed a settings
framework on every consumer would be trading their choice for a few saved lines.
A host already using ``pydantic-settings`` can still feed this model.

And the key set is *discovered* rather than derived. Appending a path to the
issuer only works for one provider; asking the issuer works for all of them. An
explicit override still wins, because an operator who names a URL has a reason.
"""

from __future__ import annotations

import os
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from ygo74.agent_runtime.domains.auth.oidc_discovery import OidcDiscovery

DEFAULT_MAX_CONVERSATIONS = 200
DEFAULT_IDLE_MINUTES = 30
DEFAULT_ROLES_CLAIM_PATH = "realm_access.roles"


class AgentHttpSettings(BaseModel):
    """The posture one agent is served with.

    Attributes:
        api_key: Demonstration mode - one key, one caller. Ignored once an issuer
            is configured: two ways in is one too many.
        oidc_issuer: The identity provider tokens are validated against.
        oidc_audience: The audience those tokens must carry.
        jwks_url_override: A key-set URL named explicitly, which wins over
            discovery.
        roles_claim_path: Where roles sit in a token.
        max_conversations: Upper bound on conversations kept in memory.
        idle_minutes: How long an untouched conversation is kept.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    api_key: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = ""
    jwks_url_override: str = ""
    roles_claim_path: str = DEFAULT_ROLES_CLAIM_PATH
    max_conversations: int = Field(default=DEFAULT_MAX_CONVERSATIONS, ge=1)
    idle_minutes: int = Field(default=DEFAULT_IDLE_MINUTES, ge=1)

    @classmethod
    def from_env(
        cls,
        prefix: str,
        *,
        default_audience: str = "",
        environment: dict[str, str] | None = None,
    ) -> Self:
        """Read the settings of one agent from prefixed environment variables.

        ``prefix`` is what distinguishes two agents served by the same process -
        ``MAIL_AGENT_HTTP_``, ``WIKI_AGENT_HTTP_``. The key-set override is also
        accepted as ``<prefix>JWKS_URL``, which is what an operator would guess.
        """
        source = environment if environment is not None else dict(os.environ)

        def read(name: str, fallback: str = "") -> str:
            return str(source.get(f"{prefix}{name}", fallback)).strip()

        def read_int(name: str, fallback: int) -> int:
            raw = read(name)
            return int(raw) if raw else fallback

        return cls(
            api_key=read("API_KEY"),
            oidc_issuer=read("OIDC_ISSUER"),
            oidc_audience=read("OIDC_AUDIENCE", default_audience),
            jwks_url_override=read("JWKS_URL") or read("JWKS_URL_OVERRIDE"),
            roles_claim_path=read("ROLES_CLAIM_PATH", DEFAULT_ROLES_CLAIM_PATH),
            max_conversations=read_int("MAX_CONVERSATIONS", DEFAULT_MAX_CONVERSATIONS),
            idle_minutes=read_int("IDLE_MINUTES", DEFAULT_IDLE_MINUTES),
        )

    @property
    def uses_oidc(self) -> bool:
        """Whether tokens are validated against an identity provider."""
        return bool(self.oidc_issuer)

    @property
    def identifies_a_caller(self) -> bool:
        """Whether anything at all would establish who is calling.

        A service that cannot answer this has no subject to partition state by,
        and would serve one person's view to whoever asked first. Hosts are
        expected to refuse to start rather than run open, which is a decision this
        model reports rather than makes.
        """
        return self.uses_oidc or bool(self.api_key)

    def jwks_url(self, discovery: OidcDiscovery | None = None) -> str:
        """Where the signing keys of the issuer are published.

        An explicit override wins. Otherwise the issuer is asked, through its
        OpenID configuration document.
        """
        if self.jwks_url_override:
            return self.jwks_url_override
        return (discovery or OidcDiscovery()).jwks_url(self.oidc_issuer)

    def idle_lifetime(self) -> timedelta:
        """How long an untouched conversation is kept."""
        return timedelta(minutes=self.idle_minutes)

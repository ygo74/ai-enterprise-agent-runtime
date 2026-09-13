"""Describing an agent to discovery, from the configuration it actually runs on.

The identity, the description and the capabilities of an agent already live in
its manifest. Writing them a second time for discovery lets the two drift, and
what a caller discovers stops matching what the agent does. So the descriptor is
derived rather than restated.

Deriving it is only worth doing if *everything* is derived. A factory that reads
the name from configuration and then asserts the authentication by hand has
simply moved the drift somewhere less visible - which is what happened to the
implementation this one replaces:

* it advertised ``("jwt", "oidc")`` unconditionally, including for a deployment
  that accepted only an API key, and for one behind no identity provider at all;
* it left ``toolInvocation`` at ``False`` while listing every skill the agent
  exposed, in the same payload.

Both facts are now taken from the values a host hands to its endpoints.
:class:`AdvertisedSecurity` is built from the very arguments that configure the
authenticator chain, so advertising a scheme the service does not accept - or
hiding one it does - requires changing two things rather than forgetting one.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
    AgentSkill,
    Modality,
)

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from ygo74.agent_runtime.domains.auth.apikey_authenticator import ApiKeyUserResolver
    from ygo74.agent_runtime.domains.auth.authenticator import Authenticator
    from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtValidationConfig

DEFAULT_VERSION = "1.0.0"
DEFAULT_OWNER = "agent-runtime"


class SecurityScheme(StrEnum):
    """An authentication scheme a deployment may accept."""

    JWT = "jwt"
    OIDC = "oidc"
    API_KEY = "apiKey"


class AdvertisedSecurity:
    """The authentication a deployment actually accepts.

    Built from the same values that configure the authenticator chain, so that
    discovery cannot advertise a scheme the service refuses, nor hide one it
    accepts.

    A deployment that authenticates nobody is refused outright rather than
    described: an agent reachable without a caller has no subject to partition
    its state by, and discovery is not the place to discover that.
    """

    def __init__(self, *, schemes: Sequence[SecurityScheme]) -> None:
        ordered = tuple(scheme for scheme in SecurityScheme if scheme in set(schemes))
        if not ordered:
            raise ValueError("a service that advertises no authentication cannot be described")
        self._schemes = ordered

    @classmethod
    def of(
        cls,
        *,
        jwt_validation: JwtValidationConfig | None,
        api_key_resolver: ApiKeyUserResolver | None,
        authenticators: Sequence[Authenticator] | None = None,
    ) -> AdvertisedSecurity:
        """Read the schemes from what a host passes to its endpoints.

        The three arguments are the three that configure the authenticator chain,
        and they are read the same way the chain reads them: an explicit
        ``authenticators`` sequence *replaces* the other two rather than adding to
        them, so the schemes are derived from it alone.

        An issuer is what distinguishes the two token schemes. Validating a
        bearer token is ``jwt``; validating one against a configured issuer means
        an identity provider is involved, which is what ``oidc`` tells a caller.
        """
        if authenticators is not None:
            return cls(schemes=[_scheme_of(authenticator) for authenticator in authenticators])

        schemes: list[SecurityScheme] = []
        if jwt_validation is not None:
            schemes.append(SecurityScheme.JWT)
            if jwt_validation.issuer:
                schemes.append(SecurityScheme.OIDC)
        if api_key_resolver is not None:
            schemes.append(SecurityScheme.API_KEY)
        return cls(schemes=schemes)

    @property
    def schemes(self) -> tuple[SecurityScheme, ...]:
        """The accepted schemes, in a stable order."""
        return self._schemes

    def names(self) -> tuple[str, ...]:
        """The scheme names as a descriptor reports them."""
        return tuple(str(scheme) for scheme in self._schemes)


# What each built-in authenticator calls itself, mapped onto what a descriptor
# advertises. The two vocabularies differ - `authType` is snake_case on the wire,
# a security scheme is camelCase - so the mapping is stated rather than guessed.
_SCHEME_BY_AUTH_TYPE: dict[str, SecurityScheme] = {
    "jwt": SecurityScheme.JWT,
    "oidc": SecurityScheme.OIDC,
    "api_key": SecurityScheme.API_KEY,
}


def _scheme_of(authenticator: Authenticator) -> SecurityScheme:
    """Map one authenticator onto the scheme a descriptor advertises.

    A custom authenticator this library has never heard of cannot be projected,
    and inventing a name for it would put a scheme in the descriptor that no
    caller can act on. The host is asked to say what it accepts instead.
    """
    scheme = _SCHEME_BY_AUTH_TYPE.get(authenticator.auth_type)
    if scheme is None:
        raise ValueError(
            f"authenticator {authenticator.auth_type!r} maps to no known security scheme; "
            "build AdvertisedSecurity explicitly for it"
        )
    return scheme


class AgentDescriptorFactory:
    """Builds the descriptor discovery advertises for one agent.

    Args:
        manifest: The configuration the agent was assembled from. Its name,
            description and skills are what discovery reports.
        agent_id: Stable identifier of the agent, used as its route key and as
            the model name an OpenAI client asks for.
        tags: How the agent is classified in a catalogue.
        created_at: When the agent was first published. Timezone-aware, so two
            deployments in different zones report the same instant.
        security: What the deployment accepts from a caller.
        streaming: Whether the surface streams. Stated by the host because it is
            an endpoint decision, not a property of the agent.
        version: Version of the agent, not of the library serving it.
        owner: Who operates the agent.
    """

    def __init__(
        self,
        manifest: AgentManifest,
        *,
        agent_id: str,
        tags: Sequence[str],
        created_at: datetime,
        security: AdvertisedSecurity,
        streaming: bool = False,
        version: str = DEFAULT_VERSION,
        owner: str = DEFAULT_OWNER,
    ) -> None:
        if not agent_id.strip():
            raise ValueError("agent_id is required to describe an agent")
        self._manifest = manifest
        self._agent_id = agent_id.strip()
        self._tags = tuple(tags)
        self._created_at = created_at
        self._security = security
        self._streaming = streaming
        self._version = version
        self._owner = owner

    def build(self) -> AgentDescriptor:
        """Build the descriptor discovery advertises."""
        return AgentDescriptor(
            agent_id=self._agent_id,
            route_key=self._agent_id,
            display_name=self._manifest.name,
            description=self._manifest.description,
            version=self._version,
            owner=self._owner,
            created_at_utc=self._created_at,
            capabilities=self._capabilities(),
            tags=self._tags,
            security_schemes=self._security.names(),
            skills=self._skills(),
        )

    def _capabilities(self) -> AgentCapabilitySet:
        """Report what the agent can do, from what it declares it does.

        ``tool_invocation`` follows the manifest rather than a default: an agent
        that declares capabilities invokes tools, and saying otherwise next to a
        list of them is a contradiction a caller has to resolve.
        """
        return AgentCapabilitySet(
            streaming=self._streaming,
            input_modalities=(Modality.TEXT,),
            output_modalities=(Modality.TEXT,),
            tool_invocation=bool(self._manifest.skills),
        )

    def _skills(self) -> tuple[AgentSkill, ...]:
        """Advertise every declared capability, in the order it is offered."""
        return tuple(
            AgentSkill(
                skill_id=skill.tool_name,
                name=skill.tool_name,
                description=skill.description,
            )
            for skill in self._manifest.skills
        )

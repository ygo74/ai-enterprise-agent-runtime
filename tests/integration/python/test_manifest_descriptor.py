"""Tests of the descriptor derived from an agent manifest.

The reason this exists is stated in one sentence: what a caller discovers must
not be able to drift from what the service actually does. The tests below are
that sentence made executable - a deployment that accepts an API key advertises
one, a deployment that exposes tools says so, and neither is asserted by hand
next to the code that could contradict it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    ApiKeyAuthenticator,
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtValidationConfig
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
from ygo74.agent_runtime.domains.discovery.manifest_descriptor import (
    AdvertisedSecurity,
    AgentDescriptorFactory,
    SecurityScheme,
)
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission

PUBLISHED_AT = datetime(2026, 9, 7, tzinfo=timezone.utc)

READ = Permission("mail", "read")


def _skill(tool_name: str) -> SkillManifest:
    return SkillManifest(
        tool_name=tool_name,
        implementation=tool_name,
        description=f"Does {tool_name}, and nothing else.",
        operation=ToolOperationDescriptor(
            tool_name=tool_name,
            operation_type=OperationType.READ,
            risk_level=RiskLevel.LOW,
            required_permission=READ,
            confirmation_required_by_default=False,
        ),
    )


def _manifest(*skills: SkillManifest) -> AgentManifest:
    return AgentManifest(
        name="Mail Agent",
        description="Works one mailbox on behalf of its caller.",
        instructions="Be precise.",
        skills=skills,
    )


def _factory(
    manifest: AgentManifest | None = None,
    *,
    security: AdvertisedSecurity | None = None,
    streaming: bool = False,
) -> AgentDescriptorFactory:
    return AgentDescriptorFactory(
        manifest if manifest is not None else _manifest(_skill("search_mail")),
        agent_id="mail-agent",
        tags=("mail",),
        created_at=PUBLISHED_AT,
        security=security if security is not None else AdvertisedSecurity(schemes=(SecurityScheme.JWT,)),
        streaming=streaming,
    )


def test_the_identity_comes_from_the_manifest() -> None:
    descriptor = _factory().build()

    assert descriptor.agent_id == "mail-agent"
    assert descriptor.route_key == "mail-agent"
    assert descriptor.display_name == "Mail Agent"
    assert descriptor.description == "Works one mailbox on behalf of its caller."
    assert descriptor.tags == ("mail",)


def test_every_declared_skill_is_advertised_in_order() -> None:
    descriptor = _factory(_manifest(_skill("search_mail"), _skill("summarise_thread"))).build()

    assert [skill.skill_id for skill in descriptor.skills] == ["search_mail", "summarise_thread"]
    assert descriptor.skills[0].description == "Does search_mail, and nothing else."


def test_an_agent_exposing_tools_says_so() -> None:
    """The defect this factory was rewritten to fix.

    Leaving ``toolInvocation`` at its default while advertising fifteen skills
    told a caller the agent invoked no tool, in the very same payload that listed
    them.
    """
    descriptor = _factory(_manifest(_skill("search_mail"))).build()

    assert descriptor.capabilities.tool_invocation


def test_an_agent_exposing_no_tool_does_not_claim_to() -> None:
    descriptor = _factory(_manifest()).build()

    assert not descriptor.capabilities.tool_invocation


def test_streaming_is_reported_as_configured() -> None:
    assert not _factory().build().capabilities.streaming
    assert _factory(streaming=True).build().capabilities.streaming


def test_a_deployment_accepting_only_an_api_key_advertises_only_that() -> None:
    """The other half of the defect: two schemes were asserted unconditionally."""
    security = AdvertisedSecurity.of(
        jwt_validation=None,
        api_key_resolver=StaticApiKeyUserResolver({"k": ResolvedUser(user_id="demo")}),
    )

    descriptor = _factory(security=security).build()

    assert descriptor.security_schemes == ("apiKey",)


def test_a_deployment_behind_a_realm_advertises_the_token_schemes() -> None:
    security = AdvertisedSecurity.of(
        jwt_validation=JwtValidationConfig(issuer="https://realm.example/auth"),
        api_key_resolver=None,
    )

    descriptor = _factory(security=security).build()

    assert descriptor.security_schemes == ("jwt", "oidc")


def test_a_bare_token_deployment_does_not_claim_an_identity_provider() -> None:
    """Without an issuer there is no OIDC discovery to speak of."""
    security = AdvertisedSecurity.of(jwt_validation=JwtValidationConfig(), api_key_resolver=None)

    assert security.names() == ("jwt",)


def test_a_deployment_accepting_both_advertises_both() -> None:
    security = AdvertisedSecurity.of(
        jwt_validation=JwtValidationConfig(issuer="https://realm.example/auth"),
        api_key_resolver=StaticApiKeyUserResolver({"k": ResolvedUser(user_id="demo")}),
    )

    assert security.names() == ("jwt", "oidc", "apiKey")


def test_a_service_that_authenticates_nobody_is_refused() -> None:
    """An agent reachable without a caller has no subject to partition state by."""
    with pytest.raises(ValueError, match="advertises no authentication"):
        AdvertisedSecurity(schemes=())


def test_an_explicit_authenticator_chain_is_read_from_the_chain() -> None:
    """`authenticators` replaces the other two arguments, so it must be read alone.

    The endpoints treat it that way; a descriptor that ignored it would advertise
    a chain the service does not run.
    """
    security = AdvertisedSecurity.of(
        jwt_validation=JwtValidationConfig(issuer="https://realm.example/auth"),
        api_key_resolver=None,
        authenticators=[ApiKeyAuthenticator(StaticApiKeyUserResolver({"k": ResolvedUser(user_id="demo")}))],
    )

    assert security.names() == ("apiKey",)


def test_an_authenticator_the_library_cannot_name_is_refused() -> None:
    """Inventing a scheme name would advertise a door no caller can open."""

    class _Custom:
        auth_type = "mutual-tls"

    with pytest.raises(ValueError, match="maps to no known security scheme"):
        AdvertisedSecurity.of(jwt_validation=None, api_key_resolver=None, authenticators=[_Custom()])  # type: ignore[list-item]


def test_a_repeated_scheme_is_advertised_once() -> None:
    resolver = StaticApiKeyUserResolver({"k": ResolvedUser(user_id="demo")})

    security = AdvertisedSecurity.of(
        jwt_validation=None,
        api_key_resolver=None,
        authenticators=[ApiKeyAuthenticator(resolver), ApiKeyAuthenticator(resolver)],
    )

    assert security.names() == ("apiKey",)


def test_the_factory_refuses_to_describe_an_agent_it_cannot_name() -> None:
    with pytest.raises(ValueError, match="agent_id"):
        AgentDescriptorFactory(
            _manifest(),
            agent_id="  ",
            tags=(),
            created_at=PUBLISHED_AT,
            security=AdvertisedSecurity(schemes=(SecurityScheme.JWT,)),
        )


def test_a_descriptor_survives_a_round_trip() -> None:
    descriptor = _factory().build()

    assert type(descriptor).from_dict(descriptor.to_dict()) == descriptor

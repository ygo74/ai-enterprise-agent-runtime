"""Resolve manifest HTTP declarations into existing security and hosting policies."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import SecretStr
from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import (
    AuthenticationPolicy,
)
from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    DiscoveredJwksKeyResolver,
    JwksKeyResolver,
    JwtValidationConfig,
    StaticPublicKeyResolver,
    StaticSymmetricKeyResolver,
)
from ygo74.agent_runtime.domains.contracts.http_configuration import (
    AgentHttpConfiguration,
    HttpEndpoint,
)

if TYPE_CHECKING:
    from ygo74.agent_runtime.domains.endpoints.rate_limiting import (
        RateLimitSettings,
    )

_ENVIRONMENT_REFERENCE = re.compile(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}$")


@dataclass(frozen=True, slots=True)
class AgentHttpRuntimeSettings:
    """Resolved HTTP settings used only when constructing an agent host.

    Args:
        endpoints: Invocation endpoints selected in the manifest.
        authentication: Existing runtime authentication policy built from the manifest.
        rate_limit: Optional resolved per-client rate-limit settings.
    """

    endpoints: tuple[HttpEndpoint, ...]
    authentication: AuthenticationPolicy
    rate_limit: RateLimitSettings | None = None

    def close(self) -> None:
        """Close resources owned by the manifest-built authentication policy."""
        self.authentication.build().close()


class AgentHttpSettingsBuilder:
    """Resolve a manifest's protected environment references at HTTP composition time.

    Loading an :class:`AgentManifest` does not call this builder. CLI and MCP
    consumers can therefore load the same manifest without HTTP credentials.

    Args:
        environment: Environment mapping used for protected references; by default the process environment is read.
    """

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        """Retain only the environment mapping needed by a later host build."""
        self._environment = environment

    def build(self, configuration: AgentHttpConfiguration) -> AgentHttpRuntimeSettings:
        """Resolve secrets and build the shared authentication and rate-limit policies.

        Args:
            configuration: Validated HTTP declaration retained by an agent manifest.
        """
        from ygo74.agent_runtime.domains.endpoints.rate_limiting import (
            RateLimitSettings,
        )

        environment = self._environment if self._environment is not None else os.environ
        authentication = self._authentication(configuration, environment)
        rate_limit_configuration = configuration.rate_limit
        rate_limit = None
        if rate_limit_configuration is not None:
            storage_uri = self._resolve_optional(
                rate_limit_configuration.storage_uri,
                environment,
                "http.rate_limit.storage_uri",
            )
            rate_limit = RateLimitSettings(
                limits=rate_limit_configuration.limits,
                storage_uri=storage_uri,
            )
        return AgentHttpRuntimeSettings(
            endpoints=configuration.endpoints,
            authentication=authentication,
            rate_limit=rate_limit,
        )

    def _authentication(
        self,
        configuration: AgentHttpConfiguration,
        environment: Mapping[str, str],
    ) -> AuthenticationPolicy:
        """Create the selected authentication policy using existing authenticators."""
        security = configuration.security
        api_key = security.api_key
        if api_key is not None:
            value = self._resolve(api_key.value, environment, "http.security.api_key.value")
            user = ResolvedUser(
                user_id=api_key.user.subject,
                username=api_key.user.username,
                name=api_key.user.name,
                email=api_key.user.email,
            )
            resolver = StaticApiKeyUserResolver({value: user})
            return AuthenticationPolicy.api_key(
                resolver,
                header_name=api_key.header_name,
            )

        jwt = security.jwt
        if jwt is None:
            raise ValueError("http.security must select a complete JWT or API key configuration")

        key_resolver = None
        if jwt.secret is not None:
            secret = self._resolve(jwt.secret, environment, "http.security.jwt.secret")
            key_resolver = StaticSymmetricKeyResolver(secret)
        elif jwt.public_key is not None:
            public_key = self._resolve(
                jwt.public_key, environment, "http.security.jwt.public_key"
            )
            key_resolver = StaticPublicKeyResolver(public_key)
        elif jwt.jwks_url is not None:
            key_resolver = JwksKeyResolver(jwt.jwks_url)
        else:
            if jwt.issuer is None:
                raise ValueError("http.security.jwt requires a key source")
            key_resolver = DiscoveredJwksKeyResolver(jwt.issuer)

        audience = jwt.audience
        validation = JwtValidationConfig(
            allowed_algorithms=jwt.allowed_algorithms,
            required_claims=jwt.required_claims,
            issuer=jwt.issuer,
            audience=list(audience) if isinstance(audience, tuple) else audience,
            leeway_seconds=jwt.leeway_seconds,
            key_resolver=key_resolver,
            roles_claim_path=jwt.roles_claim_path,
            groups_claim_path=jwt.groups_claim_path,
        )
        return AuthenticationPolicy.jwt(validation)

    def _resolve(
        self,
        reference: SecretStr,
        environment: Mapping[str, str],
        field_path: str,
    ) -> str:
        """Resolve one required ``${VARIABLE}`` without returning secret values in errors."""
        name_match = _ENVIRONMENT_REFERENCE.fullmatch(reference.get_secret_value())
        if name_match is None:
            raise ValueError(f"{field_path} must contain an environment reference")
        variable_name = name_match.group("name")
        value = environment.get(variable_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_path} requires a non-empty {variable_name} environment variable")
        return value

    def _resolve_optional(
        self,
        reference: SecretStr | None,
        environment: Mapping[str, str],
        field_path: str,
    ) -> SecretStr | None:
        """Resolve a protected storage URI while preserving its redacted wrapper."""
        if reference is None:
            return None
        raw = reference.get_secret_value()
        if _ENVIRONMENT_REFERENCE.fullmatch(raw) is None:
            return reference
        return SecretStr(self._resolve(reference, environment, field_path))

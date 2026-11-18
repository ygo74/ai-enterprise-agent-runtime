"""Typed HTTP hosting declarations embedded in ``agent.yaml``."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

_ConfigurationText = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"\S")
]
_EnvironmentReference = re.compile(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}$")
_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_RATE_LIMIT_PATTERN = r"^[1-9][0-9]*/(?:second|minute|hour|day|month|year)$"
_RATE_LIMIT = re.compile(_RATE_LIMIT_PATTERN)
_JWT_ALGORITHMS = frozenset(
    {
        "HS256",
        "HS384",
        "HS512",
        "RS256",
        "RS384",
        "RS512",
        "ES256",
        "ES384",
        "ES512",
        "PS256",
        "PS384",
        "PS512",
        "EdDSA",
    }
)


class HttpEndpoint(StrEnum):
    """Invocation endpoints that an agent manifest can activate."""

    CHAT_COMPLETIONS = "chat_completions"
    RESPONSES = "responses"
    MESSAGES = "messages"
    MCP = "mcp"


class HttpSecurityMode(StrEnum):
    """Authentication policy selected by the HTTP section of an agent manifest."""

    JWT = "jwt"
    API_KEY = "api_key"


class ApiKeyIdentityConfiguration(BaseModel):
    """Non-secret identity information attached to one configured API key.

    Args:
        subject: Stable subject identifier projected into the authenticated user context.
        email: Optional email address associated with the service identity.
        username: Optional username projected into the authenticated identity.
        name: Optional display name projected into the authenticated identity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: _ConfigurationText
    email: _ConfigurationText | None = None
    username: _ConfigurationText | None = None
    name: _ConfigurationText | None = None


class ApiKeyConfiguration(BaseModel):
    """One API key reference and the identity it authenticates.

    Args:
        value: Protected environment-variable reference containing the API key.
        header_name: HTTP header that carries the API key.
        user: Explicit identity established after the key is accepted.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: SecretStr = Field(
        json_schema_extra={
            "pattern": r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$",
            "description": "Environment variable reference containing the API key.",
        }
    )
    header_name: _ConfigurationText = "X-API-Key"
    user: ApiKeyIdentityConfiguration

    @field_validator("value")
    @classmethod
    def _require_environment_reference(cls, value: SecretStr) -> SecretStr:
        """Keep raw API keys out of the manifest and require an environment reference."""
        if _EnvironmentReference.fullmatch(value.get_secret_value()) is None:
            raise ValueError("value must be an environment reference such as ${API_KEY}")
        return value

    @field_validator("header_name")
    @classmethod
    def _validate_header_name(cls, value: str) -> str:
        """Require an RFC token header name before creating an authenticator."""
        if _HEADER_NAME.fullmatch(value) is None:
            raise ValueError("header_name must be a valid HTTP token")
        return value


class JwtConfiguration(BaseModel):
    """JWT validation and signing-key source accepted by the runtime security package.

    Exactly one key source is selected: ``jwks_url``, ``secret`` or
    ``public_key``. When none is named, ``issuer`` supplies OIDC discovery.

    Args:
        allowed_algorithms: JWT algorithms accepted by the validator.
        required_claims: Claims that must exist in every accepted token.
        issuer: Expected issuer and, when used alone as the key source, OIDC discovery issuer.
        audience: Expected audience value or values.
        leeway_seconds: Nonnegative clock-skew allowance.
        roles_claim_path: Optional dotted claim path for role projection.
        groups_claim_path: Optional dotted claim path for group projection.
        jwks_url: Direct HTTPS JSON Web Key Set URL.
        secret: Environment reference holding a static symmetric signing secret.
        public_key: Environment reference holding a static public signing key.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_algorithms: tuple[_ConfigurationText, ...] = ("HS256",)
    required_claims: tuple[_ConfigurationText, ...] = ("sub",)
    issuer: _ConfigurationText | None = None
    audience: _ConfigurationText | tuple[_ConfigurationText, ...] | None = None
    leeway_seconds: StrictInt = Field(default=0, ge=0)
    roles_claim_path: _ConfigurationText | None = None
    groups_claim_path: _ConfigurationText | None = None
    jwks_url: _ConfigurationText | None = None
    secret: SecretStr | None = Field(
        default=None,
        json_schema_extra={
            "pattern": r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$",
            "description": "Environment variable reference containing the symmetric signing secret.",
        },
    )
    public_key: SecretStr | None = Field(
        default=None,
        json_schema_extra={
            "pattern": r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$",
            "description": "Environment variable reference containing the static public key.",
        },
    )

    @field_validator("secret", "public_key")
    @classmethod
    def _validate_key_reference(cls, value: SecretStr | None) -> SecretStr | None:
        """Require static key material to come from a protected environment reference."""
        if value is not None and _EnvironmentReference.fullmatch(
            value.get_secret_value()
        ) is None:
            raise ValueError("static key material must use an environment reference")
        return value

    @model_validator(mode="after")
    def _validate_key_source_and_claim_settings(self) -> JwtConfiguration:
        """Validate JWT sources, algorithm families, URLs and duplicate claim names."""
        if not self.allowed_algorithms:
            raise ValueError("allowed_algorithms must contain at least one algorithm")
        unknown = set(self.allowed_algorithms) - _JWT_ALGORITHMS
        if unknown:
            raise ValueError("allowed_algorithms contains an unsupported algorithm")
        if len(set(self.allowed_algorithms)) != len(self.allowed_algorithms):
            raise ValueError("allowed_algorithms must not contain duplicates")
        if not self.required_claims:
            raise ValueError("required_claims must contain at least one claim")
        if len(set(self.required_claims)) != len(self.required_claims):
            raise ValueError("required_claims must not contain duplicates")

        static_sources = sum(
            source is not None for source in (self.jwks_url, self.secret, self.public_key)
        )
        if static_sources > 1:
            raise ValueError("configure exactly one JWT key source")
        if static_sources == 0 and self.issuer is None:
            raise ValueError("configure issuer discovery or one JWT key source")
        if self.secret is not None and any(
            not algorithm.startswith("HS") for algorithm in self.allowed_algorithms
        ):
            raise ValueError("allowed_algorithms for secret must use HMAC")
        if self.public_key is not None and any(
            not algorithm.startswith(("RS", "ES", "PS")) and algorithm != "EdDSA"
            for algorithm in self.allowed_algorithms
        ):
            raise ValueError("allowed_algorithms for public_key must be asymmetric")
        remote_key_source = self.jwks_url is not None or (
            self.secret is None and self.public_key is None
        )
        if remote_key_source and any(
            algorithm.startswith("HS") for algorithm in self.allowed_algorithms
        ):
            raise ValueError(
                "allowed_algorithms for remote JWKS sources must be asymmetric"
            )
        if self.issuer is not None:
            _validate_https_url(self.issuer, "issuer")
        if self.jwks_url is not None:
            _validate_https_url(self.jwks_url, "jwks_url")
        return self


class HttpSecurityConfiguration(BaseModel):
    """Select one complete, explicit JWT or API-key authentication configuration.

    Args:
        mode: Authentication mode required for every HTTP-hosted agent.
        jwt: JWT settings, required only when ``mode`` is ``jwt``.
        api_key: API-key settings, required only when ``mode`` is ``api_key``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: HttpSecurityMode
    jwt: JwtConfiguration | None = None
    api_key: ApiKeyConfiguration | None = None

    @model_validator(mode="after")
    def _require_matching_settings(self) -> HttpSecurityConfiguration:
        """Reject incomplete and mixed authentication modes."""
        if self.mode is HttpSecurityMode.JWT:
            if self.jwt is None or self.api_key is not None:
                raise ValueError("jwt mode requires jwt settings and forbids api_key settings")
            return self
        if self.api_key is None or self.jwt is not None:
            raise ValueError("api_key mode requires api_key settings and forbids jwt settings")
        return self


class RateLimitConfiguration(BaseModel):
    """Optional SlowAPI limits and protected storage URI declared for an agent.

    Args:
        limits: One or more per-client limits, such as ``60/minute``.
        storage_uri: Optional literal backend URI or protected environment reference.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    limits: tuple[
        Annotated[StrictStr, StringConstraints(pattern=_RATE_LIMIT_PATTERN)], ...
    ] = Field(min_length=1)
    storage_uri: SecretStr | None = None

    @field_validator("limits")
    @classmethod
    def _validate_limit_syntax(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Reject unsupported limit syntax before a FastAPI app is modified."""
        if any(_RATE_LIMIT.fullmatch(value) is None for value in values):
            raise ValueError("limits entries must use the form '<positive integer>/<period>'")
        if len(set(values)) != len(values):
            raise ValueError("limits must not contain duplicates")
        return values

    @field_validator("storage_uri")
    @classmethod
    def _validate_storage_uri(cls, value: SecretStr | None) -> SecretStr | None:
        """Accept a protected variable reference or a supported backend URI."""
        if value is None:
            return None
        raw = value.get_secret_value()
        if _EnvironmentReference.fullmatch(raw):
            return value
        parsed = urlsplit(raw)
        if parsed.scheme not in {"redis", "rediss", "memory"}:
            raise ValueError("storage_uri must use a supported backend URI")
        if parsed.scheme != "memory" and not parsed.hostname:
            raise ValueError("storage_uri must identify a backend host")
        return value


class McpHttpEndpointConfiguration(BaseModel):
    """HTTP settings specific to an agent's MCP operation endpoint.

    Args:
        resource_url: Canonical HTTPS resource URL, or an exact environment reference,
            advertised when MCP uses JWT authentication.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_url: _ConfigurationText | None = None

    @field_validator("resource_url")
    @classmethod
    def _validate_resource_url(cls, value: str | None) -> str | None:
        """Require a canonical HTTPS URL or a protected deployment reference."""
        if value is None or _EnvironmentReference.fullmatch(value) is not None:
            return value
        _validate_https_url(value, "http.mcp.resource_url")
        return value


class AgentHttpConfiguration(BaseModel):
    """HTTP endpoint, security, and optional rate-limit declaration for one agent.

    Args:
        endpoints: One or more supported invocation endpoints activated by the host.
        security: Required authentication policy for all enabled invocation routes.
        mcp: Optional settings for the MCP endpoint.
        rate_limit: Optional limit applied to enabled invocation routes only.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    endpoints: tuple[HttpEndpoint, ...] = Field(min_length=1)
    security: HttpSecurityConfiguration
    mcp: McpHttpEndpointConfiguration | None = None
    rate_limit: RateLimitConfiguration | None = None

    @model_validator(mode="after")
    def _require_unique_endpoints(self) -> AgentHttpConfiguration:
        """Require unique endpoints and complete settings for protected MCP."""
        if len(set(self.endpoints)) != len(self.endpoints):
            raise ValueError("endpoints must not contain duplicates")
        if self.mcp is not None and HttpEndpoint.MCP not in self.endpoints:
            raise ValueError("http.mcp settings require the mcp endpoint")
        if (
            HttpEndpoint.MCP in self.endpoints
            and self.security.mode is HttpSecurityMode.JWT
            and (self.mcp is None or self.mcp.resource_url is None)
        ):
            raise ValueError(
                "http.mcp.resource_url is required for JWT-authenticated MCP"
            )
        return self


def _validate_https_url(value: str, field_name: str) -> None:
    """Require an HTTPS URL without user-info for an issuer or JWKS endpoint."""
    parsed = urlsplit(value)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{field_name} must be an HTTPS URL without credentials, query, or fragment"
        )

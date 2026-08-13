from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

import jwt
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAlgorithmError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    MissingRequiredClaimError,
    PyJWKClient,
)
from jwt.exceptions import PyJWKClientError

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError


class JwtKeyResolver(Protocol):
    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        ...


@dataclass(slots=True)
class StaticSymmetricKeyResolver:
    secret: str

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        _ = (token, unverified_header)
        return self.secret


@dataclass(slots=True)
class StaticPublicKeyResolver:
    public_key: str

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        _ = (token, unverified_header)
        return self.public_key


@dataclass(slots=True)
class RotatingKeyResolver:
    keys_by_kid: dict[str, Any]
    default_key: Any | None = None

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        _ = token
        kid = unverified_header.get("kid")
        if isinstance(kid, str) and kid in self.keys_by_kid:
            return self.keys_by_kid[kid]
        if self.default_key is not None:
            return self.default_key
        raise AuthenticationError(
            code="signing_key_unavailable",
            message="No signing key available for JWT key identifier",
            details={"kid": kid},
        )


@dataclass(slots=True)
class JwksKeyResolver:
    jwks_url: str
    cache_ttl_seconds: int = 300
    _client: PyJWKClient | None = field(default=None, init=False, repr=False)

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        _ = unverified_header
        if self._client is None:
            self._client = PyJWKClient(self.jwks_url, cache_jwk_set=True, lifespan=self.cache_ttl_seconds)

        try:
            signing_key = self._client.get_signing_key_from_jwt(token)
            return signing_key.key
        except PyJWKClientError as ex:
            raise AuthenticationError(
                code="signing_key_unavailable",
                message="Unable to resolve signing key from JWKS",
            ) from ex


@dataclass(slots=True)
class JwtValidationConfig:
    allowed_algorithms: tuple[str, ...] = ("HS256",)
    required_claims: tuple[str, ...] = ("sub",)
    issuer: str | None = None
    audience: str | list[str] | tuple[str, ...] | None = None
    leeway_seconds: int = 0
    key_resolver: JwtKeyResolver | None = None


def authenticate_authorization_header(
    authorization_header: str | None,
    config: JwtValidationConfig,
) -> dict[str, Any]:
    if authorization_header is None:
        raise AuthenticationError(
            code="authorization_header_missing",
            message="Missing Authorization header",
        )

    scheme, _, credentials = authorization_header.partition(" ")
    if not scheme:
        raise AuthenticationError(
            code="malformed_authorization_header",
            message="Malformed Authorization header",
        )

    if scheme.lower() != "bearer":
        raise AuthenticationError(
            code="authorization_scheme_invalid",
            message="Authorization scheme must be Bearer",
            details={"scheme": scheme},
        )

    token = credentials.strip()
    if not token:
        raise AuthenticationError(
            code="token_missing",
            message="Bearer token is missing",
        )

    return authenticate_jwt(token, config)


def authenticate_jwt(token: str, config: JwtValidationConfig) -> dict[str, Any]:
    if not token:
        raise AuthenticationError(code="token_missing", message="Bearer token is missing")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except DecodeError as ex:
        raise AuthenticationError(code="token_malformed", message="JWT token is malformed") from ex

    algorithm = unverified_header.get("alg")
    if not isinstance(algorithm, str):
        raise AuthenticationError(code="algorithm_missing", message="JWT header algorithm is missing")

    if algorithm not in config.allowed_algorithms:
        raise AuthenticationError(
            code="algorithm_not_allowed",
            message="JWT algorithm is not allowed",
            details={"algorithm": algorithm, "allowed_algorithms": list(config.allowed_algorithms)},
        )

    key = _resolve_signing_key(token, unverified_header, config)

    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[algorithm],
            issuer=config.issuer,
            audience=config.audience,
            leeway=config.leeway_seconds,
            options={"require": list(config.required_claims)},
        )
    except ExpiredSignatureError as ex:
        raise AuthenticationError(code="token_expired", message="JWT token has expired") from ex
    except ImmatureSignatureError as ex:
        raise AuthenticationError(code="token_not_yet_valid", message="JWT token is not active yet") from ex
    except InvalidIssuerError as ex:
        raise AuthenticationError(code="issuer_invalid", message="JWT issuer is invalid") from ex
    except InvalidAudienceError as ex:
        raise AuthenticationError(code="audience_invalid", message="JWT audience is invalid") from ex
    except MissingRequiredClaimError as ex:
        raise AuthenticationError(
            code="required_claim_missing",
            message="JWT required claim is missing",
            details={"claim": ex.claim},
        ) from ex
    except InvalidSignatureError as ex:
        raise AuthenticationError(code="signature_invalid", message="JWT signature is invalid") from ex
    except (InvalidAlgorithmError, DecodeError) as ex:
        raise AuthenticationError(code="token_malformed", message="JWT token is malformed") from ex

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise AuthenticationError(
            code="required_claim_missing",
            message="JWT subject claim is missing",
            details={"claim": "sub"},
        )

    context_claims = _extract_context_claims(claims)

    return {
        "authType": "jwt",
        "identity": {
            "subject": subject,
            "userId": subject,
        },
        "claims": context_claims,
    }


def _resolve_signing_key(token: str, unverified_header: Mapping[str, Any], config: JwtValidationConfig) -> Any:
    if config.key_resolver is None:
        raise AuthenticationError(
            code="signing_key_unavailable",
            message="JWT signing key resolver is not configured",
        )

    return config.key_resolver.resolve_key(token, unverified_header)


def _extract_context_claims(claims: Mapping[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key in ("iss", "aud", "exp", "nbf", "iat", "jti", "scope", "roles"):
        if key in claims:
            projected[key] = claims[key]
    return projected

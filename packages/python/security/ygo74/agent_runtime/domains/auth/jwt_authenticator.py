from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

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
from ygo74.agent_runtime.domains.auth.auth_context import AuthenticatedUserContext
from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.authenticator import Authenticator
from ygo74.agent_runtime.domains.auth.claims_projection import ClaimsProjector
from ygo74.agent_runtime.domains.auth.oidc_discovery import OidcDiscovery


class JwtKeyResolver(Protocol):
    """Resolve JWT credentials from configured sources while enforcing documented selection rules.
    """
    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        """Resolve key using configuration and registered candidates.

        Args:
            token (str): The credential token to parse and authenticate.
            unverified_header (Mapping[str, Any]): Decoded JWT header used only to select a candidate signing key before verification.
        """
        ...


@dataclass(slots=True)
class StaticSymmetricKeyResolver(JwtKeyResolver):
    """Resolve JWT credentials from configured sources while enforcing documented selection rules.

    Args:
        secret (str): Symmetric signing secret held by the configured key resolver.
    """
    secret: str

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        """Resolve key using configuration and registered candidates.

        Args:
            token (str): The credential token to parse and authenticate.
            unverified_header (Mapping[str, Any]): Decoded JWT header used only to select a candidate signing key before verification.
        """
        _ = (token, unverified_header)
        return self.secret


@dataclass(slots=True)
class StaticPublicKeyResolver(JwtKeyResolver):
    """Resolve JWT credentials from configured sources while enforcing documented selection rules.

    Args:
        public_key (str): Public signing key used to validate JWT signatures.
    """
    public_key: str

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        """Resolve key using configuration and registered candidates.

        Args:
            token (str): The credential token to parse and authenticate.
            unverified_header (Mapping[str, Any]): Decoded JWT header used only to select a candidate signing key before verification.
        """
        _ = (token, unverified_header)
        return self.public_key


@dataclass(slots=True)
class RotatingKeyResolver(JwtKeyResolver):
    """Resolve JWT credentials from configured sources while enforcing documented selection rules.

    Args:
        keys_by_kid (dict[str, Any]): Signing keys indexed by their JWT key identifier.
        default_key (Any | None): Signing key used when the JWT header has no key identifier.
    """
    keys_by_kid: dict[str, Any]
    default_key: Any | None = None

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        """Resolve key using configuration and registered candidates.

        Args:
            token (str): The credential token to parse and authenticate.
            unverified_header (Mapping[str, Any]): Decoded JWT header used only to select a candidate signing key before verification.
        """
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
class JwksKeyResolver(JwtKeyResolver):
    """Resolve JWT credentials from configured sources while enforcing documented selection rules.

    Args:
        jwks_url (str): Configured JSON Web Key Set endpoint for public signing keys.
        cache_ttl_seconds (int): How long resolved signing keys remain in the local cache.
        _client (PyJWKClient | None): HTTP or SDK client used to retrieve signing keys or discovery data.
    """
    jwks_url: str
    cache_ttl_seconds: int = 300
    _client: PyJWKClient | None = field(default=None, init=False, repr=False)

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        """Resolve key using configuration and registered candidates.

        Args:
            token (str): The credential token to parse and authenticate.
            unverified_header (Mapping[str, Any]): Decoded JWT header used only to select a candidate signing key before verification.
        """
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
class DiscoveredJwksKeyResolver(JwtKeyResolver):
    """Finds the issuer's key set by asking it, on first use.

    :class:`JwksKeyResolver` needs the key-set URL at construction, which forces a
    host to discover it while reading configuration. That is the wrong moment twice
    over: a server would fail to start because its identity provider was briefly
    unreachable, and reading configuration would need a network - so a test could
    not do it at all.

    Discovery happens on the first token instead, which is also when the key set
    itself is fetched. An operator who names the URL explicitly should use
    :class:`JwksKeyResolver` directly; asking the issuer is for everyone else,
    because appending a path to an issuer only works for one provider.

    Args:
        issuer (str): Expected JWT or OIDC issuer.
        discovery (OidcDiscovery): Discovery settings and registry used to expose agent metadata.
        cache_ttl_seconds (int): How long resolved signing keys remain in the local cache.
        _delegate (JwksKeyResolver | None): Underlying resolver delegated the signing-key lookup.
    """
    issuer: str
    discovery: OidcDiscovery = field(default_factory=lambda: OidcDiscovery())
    cache_ttl_seconds: int = 300
    _delegate: JwksKeyResolver | None = field(default=None, init=False, repr=False)

    def resolve_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        """Resolve key using configuration and registered candidates.

        Args:
            token (str): The credential token to parse and authenticate.
            unverified_header (Mapping[str, Any]): Decoded JWT header used only to select a candidate signing key before verification.
        """
        if self._delegate is None:
            self._delegate = JwksKeyResolver(
                jwks_url=self.discovery.jwks_url(self.issuer),
                cache_ttl_seconds=self.cache_ttl_seconds,
            )
        return self._delegate.resolve_key(token, unverified_header)


@dataclass(slots=True)
class JwtValidationConfig:
    """Validated JWT settings covering algorithms, issuer, audience, required claims, clock leeway, and signing-key resolution.

    Args:
        allowed_algorithms (tuple[str, ...]): JWT algorithms explicitly accepted by the validator.
        required_claims (tuple[str, ...]): JWT claims that must be present for authentication.
        issuer (str | None): Expected JWT or OIDC issuer.
        audience (str | list[str] | tuple[str, ...] | None): Expected JWT audience identifying this API.
        leeway_seconds (int): Clock-skew allowance used when validating JWT timestamps.
        key_resolver (JwtKeyResolver | None): Signing-key resolver used after reading the unverified JWT header.
        roles_claim_path (str | None): Dotted claim path from which role values are read.
        groups_claim_path (str | None): Dotted claim path from which group values are read.
    """
    allowed_algorithms: tuple[str, ...] = ("HS256",)
    required_claims: tuple[str, ...] = ("sub",)
    issuer: str | None = None
    audience: str | list[str] | tuple[str, ...] | None = None
    leeway_seconds: int = 0
    key_resolver: JwtKeyResolver | None = None
    roles_claim_path: str | None = None
    groups_claim_path: str | None = None


class JwtAuthenticator(Authenticator):
    """Authenticates callers presenting a Bearer JWT in the Authorization header.

    Args:
        config (JwtValidationConfig | None): The configuration values that constrain this behavior.
    """
    HEADER_NAME = "authorization"
    SCHEME = "bearer"

    def __init__(self, config: JwtValidationConfig | None = None) -> None:
        """Initialize the instance JWT credentials with supplied collaborators and configuration.

        Args:
            config (JwtValidationConfig | None): The configuration values that constrain this behavior.
        """
        self._config = config or JwtValidationConfig()
        self._projector = ClaimsProjector(
            roles_claim_path=self._config.roles_claim_path,
            groups_claim_path=self._config.groups_claim_path,
        )

    @property
    def auth_type(self) -> str:
        """Return the authentication mechanism name JWT credentials used for diagnostics and policy decisions.
        """
        return "jwt"

    @property
    def config(self) -> JwtValidationConfig:
        """Return the immutable JWT validation settings used by this authenticator.
        """
        return self._config

    def can_authenticate(self, headers: Mapping[str, Any]) -> bool:
        """Determine whether the authenticator accepts this credential form JWT credentials before verification.

        Args:
            headers (Mapping[str, Any]): The request headers used for protocol selection, forwarding, or authentication.
        """
        return headers.get(self.HEADER_NAME) is not None

    def missing_credential_error(self) -> AuthenticationError:
        """Create the missing-credential error JWT credentials with scheme-specific response details.
        """
        return AuthenticationError(
            code="authorization_header_missing",
            message="Missing Authorization header",
        )

    def authenticate(self, headers: Mapping[str, Any]) -> AuthenticatedUserContext:
        """Authenticate JWT credentials and return identity context or a structured failure.

        Args:
            headers (Mapping[str, Any]): The request headers used for protocol selection, forwarding, or authentication.
        """
        return self.authenticate_header(headers.get(self.HEADER_NAME))

    def authenticate_header(self, authorization_header: str | None) -> AuthenticatedUserContext:
        """Authenticate header and return identity context or a structured failure.

        Args:
            authorization_header (str | None): Raw Authorization header containing the optional Bearer token.
        """
        if authorization_header is None:
            raise self.missing_credential_error()

        scheme, _, credentials = authorization_header.partition(" ")
        if not scheme:
            raise AuthenticationError(
                code="malformed_authorization_header",
                message="Malformed Authorization header",
            )

        if scheme.lower() != self.SCHEME:
            raise AuthenticationError(
                code="authorization_scheme_invalid",
                message="Authorization scheme must be Bearer",
                details={"scheme": scheme},
            )

        token = credentials.strip()
        if not token:
            raise AuthenticationError(code="token_missing", message="Bearer token is missing")

        return self.authenticate_token(token)

    def authenticate_token(self, token: str) -> AuthenticatedUserContext:
        """Authenticate token and return identity context or a structured failure.

        Args:
            token (str): The credential token to parse and authenticate.
        """
        if not token:
            raise AuthenticationError(code="token_missing", message="Bearer token is missing")

        unverified_header = self._read_header(token)
        algorithm = self._validate_algorithm(unverified_header)
        key = self._resolve_signing_key(token, unverified_header)
        claims = self._decode(token, key, algorithm)
        subject = self._read_subject(claims)

        return AuthenticatedUserContext(
            auth_type=self.auth_type,
            identity=self._projector.identity(claims, subject),
            roles=self._projector.roles(claims),
            groups=self._projector.groups(claims),
            scopes=self._projector.scopes(claims),
            claims=self._projector.context_claims(claims),
        )

    def _read_header(self, token: str) -> Mapping[str, Any]:
        """Read the Bearer credential from the Authorization header and reject malformed schemes.

        Args:
            token (str): The credential token to parse and authenticate.
        """
        try:
            return jwt.get_unverified_header(token)
        except DecodeError as ex:
            raise AuthenticationError(code="token_malformed", message="JWT token is malformed") from ex

    def _validate_algorithm(self, unverified_header: Mapping[str, Any]) -> str:
        """Reject JWT algorithms outside the explicit allow-list before signature validation.

        Args:
            unverified_header (Mapping[str, Any]): Decoded JWT header used only to select a candidate signing key before verification.
        """
        algorithm = unverified_header.get("alg")
        if not isinstance(algorithm, str):
            raise AuthenticationError(code="algorithm_missing", message="JWT header algorithm is missing")

        if algorithm not in self._config.allowed_algorithms:
            raise AuthenticationError(
                code="algorithm_not_allowed",
                message="JWT algorithm is not allowed",
                details={
                    "algorithm": algorithm,
                    "allowed_algorithms": list(self._config.allowed_algorithms),
                },
            )

        return algorithm

    def _resolve_signing_key(self, token: str, unverified_header: Mapping[str, Any]) -> Any:
        """Choose a signing key from the token header through the configured key resolver.

        Args:
            token (str): The credential token to parse and authenticate.
            unverified_header (Mapping[str, Any]): Decoded JWT header used only to select a candidate signing key before verification.
        """
        if self._config.key_resolver is None:
            raise AuthenticationError(
                code="signing_key_unavailable",
                message="JWT signing key resolver is not configured",
            )

        return self._config.key_resolver.resolve_key(token, unverified_header)

    def _decode(self, token: str, key: Any, algorithm: str) -> dict[str, Any]:
        """Verify the JWT signature and required claims using the resolved signing key and validation policy.

        Args:
            token (str): The credential token to parse and authenticate.
            key (Any): The identifier used to locate the corresponding registered value.
            algorithm (str): JWT signing algorithm allowed by the validation policy.
        """
        try:
            return jwt.decode(
                token,
                key=key,
                algorithms=[algorithm],
                issuer=self._config.issuer,
                audience=self._config.audience,
                leeway=self._config.leeway_seconds,
                options={"require": list(self._config.required_claims)},
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

    def _read_subject(self, claims: Mapping[str, Any]) -> str:
        """Require and return the verified subject claim as the principal identity.

        Args:
            claims (Mapping[str, Any]): The validated identity claims to project into runtime context.
        """
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError(
                code="required_claim_missing",
                message="JWT subject claim is missing",
                details={"claim": "sub"},
            )

        return subject

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    JwtAuthenticator,
    JwtValidationConfig,
    RotatingKeyResolver,
    StaticSymmetricKeyResolver,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _base_claims(now: datetime) -> dict[str, object]:
    return {
        "sub": "user-123",
        "iss": "https://issuer.example.com",
        "aud": "runtime",
        "iat": int(now.timestamp()),
        "nbf": int((now - timedelta(seconds=2)).timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }


def _config(secret: str = "secret", *, leeway_seconds: int = 0) -> JwtValidationConfig:
    return JwtValidationConfig(
        allowed_algorithms=("HS256",),
        required_claims=("sub", "exp", "nbf", "iss", "aud"),
        issuer="https://issuer.example.com",
        audience="runtime",
        leeway_seconds=leeway_seconds,
        key_resolver=StaticSymmetricKeyResolver(secret),
    )


def _authenticator(secret: str = "secret", *, leeway_seconds: int = 0) -> JwtAuthenticator:
    return JwtAuthenticator(_config(secret, leeway_seconds=leeway_seconds))


def test_jwt_valid(now: datetime) -> None:
    token = jwt.encode(_base_claims(now), "secret", algorithm="HS256")

    ctx = _authenticator().authenticate_token(token)

    assert ctx.user_id == "user-123"
    assert ctx.auth_type == "jwt"
    assert ctx.claims["iss"] == "https://issuer.example.com"


def test_jwt_profile_and_roles_from_configurable_path(now: datetime) -> None:
    claims = _base_claims(now)
    claims.update(
        {
            "name": "Yannick GOBERT",
            "given_name": "Yannick",
            "family_name": "GOBERT",
            "preferred_username": "admin",
            "email": "admin@example.com",
            "email_verified": True,
            "realm_access": {"roles": ["offline_access", "admin", "uma_authorization"]},
            "resource_access": {"librechat": {"roles": ["admin"]}},
            "groups": ["/enterprise/agents"],
            "scope": "openid profile email",
        }
    )
    token = jwt.encode(claims, "secret", algorithm="HS256")
    config = _config()
    config.roles_claim_path = "resource_access.librechat.roles"
    config.groups_claim_path = "groups"

    ctx = JwtAuthenticator(config).authenticate_token(token)

    assert ctx.identity.name == "Yannick GOBERT"
    assert ctx.identity.given_name == "Yannick"
    assert ctx.identity.family_name == "GOBERT"
    assert ctx.identity.email == "admin@example.com"
    assert ctx.identity.username == "admin"
    assert ctx.roles == ["admin"]
    assert ctx.groups == ["/enterprise/agents"]
    assert ctx.scopes == ["openid", "profile", "email"]
    assert ctx.has_role("admin")
    assert ctx.claims["realm_access"]["roles"] == ["offline_access", "admin", "uma_authorization"]


def test_jwt_roles_default_to_empty_without_configured_path(now: datetime) -> None:
    claims = _base_claims(now)
    claims["realm_access"] = {"roles": ["admin"]}
    token = jwt.encode(claims, "secret", algorithm="HS256")

    ctx = _authenticator().authenticate_token(token)

    assert ctx.roles == []
    assert ctx.groups == []


def test_jwt_context_dict_matches_contract_shape(now: datetime) -> None:
    token = jwt.encode(_base_claims(now), "secret", algorithm="HS256")

    context = _authenticator().authenticate_token(token).to_dict()

    assert context["authType"] == "jwt"
    assert context["userId"] == "user-123"
    assert context["identity"]["userId"] == "user-123"


def test_jwt_expired(now: datetime) -> None:
    claims = _base_claims(now)
    claims["exp"] = int((now - timedelta(seconds=1)).timestamp())
    token = jwt.encode(claims, "secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_token(token)

    assert exc.value.code == "token_expired"


def test_jwt_invalid_signature(now: datetime) -> None:
    token = jwt.encode(_base_claims(now), "wrong-secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_token(token)

    assert exc.value.code == "signature_invalid"


def test_jwt_invalid_issuer(now: datetime) -> None:
    claims = _base_claims(now)
    claims["iss"] = "https://other-issuer.example.com"
    token = jwt.encode(claims, "secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_token(token)

    assert exc.value.code == "issuer_invalid"


def test_jwt_invalid_audience(now: datetime) -> None:
    claims = _base_claims(now)
    claims["aud"] = "other-runtime"
    token = jwt.encode(claims, "secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_token(token)

    assert exc.value.code == "audience_invalid"


def test_jwt_algorithm_not_allowed(now: datetime) -> None:
    token = jwt.encode(_base_claims(now), "secret", algorithm="HS384")

    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_token(token)

    assert exc.value.code == "algorithm_not_allowed"


def test_jwt_malformed() -> None:
    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_token("not-a-jwt")

    assert exc.value.code == "token_malformed"


def test_authorization_header_absent() -> None:
    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_header(None)

    assert exc.value.code == "authorization_header_missing"


def test_authorization_header_non_bearer() -> None:
    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_header("Basic abc123")

    assert exc.value.code == "authorization_scheme_invalid"


def test_can_authenticate_only_with_authorization_header() -> None:
    authenticator = _authenticator()

    assert authenticator.can_authenticate({"authorization": "Bearer abc"}) is True
    assert authenticator.can_authenticate({"x-api-key": "abc"}) is False


def test_claims_required_missing(now: datetime) -> None:
    claims = _base_claims(now)
    claims.pop("sub")
    token = jwt.encode(claims, "secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        _authenticator().authenticate_token(token)

    assert exc.value.code == "required_claim_missing"


def test_clock_skew_supported(now: datetime) -> None:
    claims = _base_claims(now)
    claims["nbf"] = int((now + timedelta(seconds=2)).timestamp())
    token = jwt.encode(claims, "secret", algorithm="HS256")

    ctx = _authenticator(leeway_seconds=5).authenticate_token(token)

    assert ctx.identity.subject == "user-123"


def test_key_rotation_with_kid(now: datetime) -> None:
    resolver = RotatingKeyResolver(keys_by_kid={"old": "secret-old", "new": "secret-new"})
    authenticator = JwtAuthenticator(
        JwtValidationConfig(
            allowed_algorithms=("HS256",),
            required_claims=("sub", "exp", "nbf", "iss", "aud"),
            issuer="https://issuer.example.com",
            audience="runtime",
            key_resolver=resolver,
        )
    )

    token_old = jwt.encode(_base_claims(now), "secret-old", algorithm="HS256", headers={"kid": "old"})
    token_new = jwt.encode(_base_claims(now), "secret-new", algorithm="HS256", headers={"kid": "new"})

    assert authenticator.authenticate_token(token_old).user_id == "user-123"
    assert authenticator.authenticate_token(token_new).user_id == "user-123"

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    JwtValidationConfig,
    RotatingKeyResolver,
    StaticSymmetricKeyResolver,
    authenticate_authorization_header,
    authenticate_jwt,
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


def test_jwt_valid(now: datetime) -> None:
    token = jwt.encode(_base_claims(now), "secret", algorithm="HS256")

    ctx = authenticate_jwt(token, _config())

    assert ctx["identity"]["userId"] == "user-123"
    assert ctx["claims"]["iss"] == "https://issuer.example.com"


def test_jwt_expired(now: datetime) -> None:
    claims = _base_claims(now)
    claims["exp"] = int((now - timedelta(seconds=1)).timestamp())
    token = jwt.encode(claims, "secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        authenticate_jwt(token, _config())

    assert exc.value.code == "token_expired"


def test_jwt_invalid_signature(now: datetime) -> None:
    token = jwt.encode(_base_claims(now), "wrong-secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        authenticate_jwt(token, _config())

    assert exc.value.code == "signature_invalid"


def test_jwt_invalid_issuer(now: datetime) -> None:
    claims = _base_claims(now)
    claims["iss"] = "https://other-issuer.example.com"
    token = jwt.encode(claims, "secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        authenticate_jwt(token, _config())

    assert exc.value.code == "issuer_invalid"


def test_jwt_invalid_audience(now: datetime) -> None:
    claims = _base_claims(now)
    claims["aud"] = "other-runtime"
    token = jwt.encode(claims, "secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        authenticate_jwt(token, _config())

    assert exc.value.code == "audience_invalid"


def test_jwt_algorithm_not_allowed(now: datetime) -> None:
    token = jwt.encode(_base_claims(now), "secret", algorithm="HS384")

    with pytest.raises(AuthenticationError) as exc:
        authenticate_jwt(token, _config())

    assert exc.value.code == "algorithm_not_allowed"


def test_jwt_malformed() -> None:
    with pytest.raises(AuthenticationError) as exc:
        authenticate_jwt("not-a-jwt", _config())

    assert exc.value.code == "token_malformed"


def test_authorization_header_absent() -> None:
    with pytest.raises(AuthenticationError) as exc:
        authenticate_authorization_header(None, _config())

    assert exc.value.code == "authorization_header_missing"


def test_authorization_header_non_bearer() -> None:
    with pytest.raises(AuthenticationError) as exc:
        authenticate_authorization_header("Basic abc123", _config())

    assert exc.value.code == "authorization_scheme_invalid"


def test_claims_required_missing(now: datetime) -> None:
    claims = _base_claims(now)
    claims.pop("sub")
    token = jwt.encode(claims, "secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc:
        authenticate_jwt(token, _config())

    assert exc.value.code == "required_claim_missing"


def test_clock_skew_supported(now: datetime) -> None:
    claims = _base_claims(now)
    claims["nbf"] = int((now + timedelta(seconds=2)).timestamp())
    token = jwt.encode(claims, "secret", algorithm="HS256")

    ctx = authenticate_jwt(token, _config(leeway_seconds=5))

    assert ctx["identity"]["subject"] == "user-123"


def test_key_rotation_with_kid(now: datetime) -> None:
    resolver = RotatingKeyResolver(keys_by_kid={"old": "secret-old", "new": "secret-new"})
    config = JwtValidationConfig(
        allowed_algorithms=("HS256",),
        required_claims=("sub", "exp", "nbf", "iss", "aud"),
        issuer="https://issuer.example.com",
        audience="runtime",
        key_resolver=resolver,
    )

    token_old = jwt.encode(_base_claims(now), "secret-old", algorithm="HS256", headers={"kid": "old"})
    token_new = jwt.encode(_base_claims(now), "secret-new", algorithm="HS256", headers={"kid": "new"})

    ctx_old = authenticate_jwt(token_old, config)
    ctx_new = authenticate_jwt(token_new, config)

    assert ctx_old["identity"]["userId"] == "user-123"
    assert ctx_new["identity"]["userId"] == "user-123"

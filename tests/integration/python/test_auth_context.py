import jwt

from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    JwtValidationConfig,
    StaticSymmetricKeyResolver,
    authenticate_jwt,
)


def test_jwt_auth_context() -> None:
    token = jwt.encode({"sub": "user-1"}, "secret-1", algorithm="HS256")
    config = JwtValidationConfig(key_resolver=StaticSymmetricKeyResolver("secret-1"))

    ctx = authenticate_jwt(token, config)

    assert ctx["authType"] == "jwt"
    assert ctx["identity"]["userId"] == "user-1"

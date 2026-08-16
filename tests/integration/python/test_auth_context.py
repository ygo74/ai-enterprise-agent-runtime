import jwt

from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    JwtAuthenticator,
    JwtValidationConfig,
    StaticSymmetricKeyResolver,
)


def test_jwt_auth_context() -> None:
    token = jwt.encode({"sub": "user-1"}, "secret-1", algorithm="HS256")
    authenticator = JwtAuthenticator(JwtValidationConfig(key_resolver=StaticSymmetricKeyResolver("secret-1")))

    ctx = authenticator.authenticate_token(token)

    assert ctx.auth_type == "jwt"
    assert ctx.user_id == "user-1"
    assert ctx.to_dict()["identity"]["userId"] == "user-1"

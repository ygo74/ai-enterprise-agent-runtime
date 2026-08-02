from ygo74.agent_runtime.domains.auth.jwt_authenticator import authenticate_jwt


def test_jwt_auth_context() -> None:
    ctx = authenticate_jwt("token", "user-1")
    assert ctx["authType"] == "jwt"

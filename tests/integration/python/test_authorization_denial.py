from ygo74.agent_runtime.domains.auth.auth_errors import auth_error


def test_authorization_denial_error_shape() -> None:
    err = auth_error("forbidden", "access denied", "authorization")
    assert err["code"] == "forbidden"
    assert err["category"] == "authorization"

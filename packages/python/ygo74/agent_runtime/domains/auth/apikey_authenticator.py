from collections.abc import Callable


def authenticate_api_key(api_key: str, resolver: Callable[[str], dict[str, str] | None]) -> dict[str, str]:
    user = resolver(api_key)
    if not user:
        raise ValueError("invalid api key")
    user.setdefault("authType", "api_key")
    return user

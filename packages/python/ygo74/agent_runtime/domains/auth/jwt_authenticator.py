def authenticate_jwt(token: str, user_id: str) -> dict[str, str]:
    if not token:
        raise ValueError("missing token")
    return {"userId": user_id, "authType": "jwt"}

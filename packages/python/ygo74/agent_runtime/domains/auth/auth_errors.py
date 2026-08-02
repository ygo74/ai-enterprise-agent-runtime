def auth_error(code: str, message: str, category: str) -> dict[str, str]:
    return {"code": code, "category": category, "message": message}

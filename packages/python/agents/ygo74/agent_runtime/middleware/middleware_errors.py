def middleware_error(message: str) -> dict[str, str]:
    return {
        "code": "middleware_failure",
        "category": "mapping",
        "message": message,
    }

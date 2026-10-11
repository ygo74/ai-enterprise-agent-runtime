def middleware_error(message: str) -> dict[str, str]:
    """Provide the middleware error operation for runtime data, preserving the runtime contract and validation rules.

    Args:
        message (str): Framework message or protocol message being converted.
    """
    return {
        "code": "middleware_failure",
        "category": "mapping",
        "message": message,
    }

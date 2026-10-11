def routing_error(route_key: str) -> dict[str, str]:
    """Provide the routing error operation for runtime data, preserving the runtime contract and validation rules.

    Args:
        route_key (str): The registered route key identifying the target agent or handler.
    """
    return {
        "code": "route_not_registered",
        "category": "routing",
        "message": f"No handler registered for route '{route_key}'",
    }

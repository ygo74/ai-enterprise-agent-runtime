def routing_error(route_key: str) -> dict[str, str]:
    return {
        "code": "route_not_registered",
        "category": "routing",
        "message": f"No handler registered for route '{route_key}'",
    }

from typing import Any


def map_response(endpoint_type: str, exchange_response: dict[str, Any]) -> dict[str, Any]:
    status = exchange_response.get("status", "error")
    base = {
        "request_id": exchange_response.get("request_id"),
        "status": status,
        "endpoint_type": endpoint_type,
    }

    if status == "success":
        base["output"] = exchange_response.get("output")
    else:
        base["error"] = exchange_response.get("error", {"code": "unknown", "message": "unknown error"})

    return base

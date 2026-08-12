from typing import Any


def complete_event(request_id: str, final_output: Any) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "event_type": "completion",
        "final_output": final_output,
    }


def error_event(request_id: str, error: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "event_type": "error",
        "error": error,
    }

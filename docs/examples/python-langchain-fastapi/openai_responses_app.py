from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent_solution_architect import run_solution_architect_agent
from ygo74.agent_runtime.domains.mapping.request_mapper import map_to_exchange
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response


class OpenAIResponsesRequest(BaseModel):
    model: str = Field(default="gpt-4o-mini")
    input: Any
    metadata: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


app = FastAPI(title="AI Solution Architect - OpenAI Responses Example")


@app.post("/v1/responses")
async def openai_responses(req: OpenAIResponsesRequest) -> dict[str, Any]:
    """
    Example endpoint exposed as OpenAI Responses and routed through ygo74 runtime mapping.
    """

    payload = {
        "request_id": req.metadata.get("request_id", "req-demo-001"),
        "route_key": req.metadata.get("route_key", "ai-solution-architect"),
        "model": req.model,
        "input": req.input,
        "metadata": req.metadata,
        "stream": req.stream,
    }

    try:
        exchange_req = map_to_exchange("openai.responses", payload)

        if isinstance(exchange_req.input, list):
            user_input = "\n".join(str(item) for item in exchange_req.input)
        else:
            user_input = str(exchange_req.input)

        architect_output = await run_solution_architect_agent(user_input)

        exchange_response = {
            "request_id": exchange_req.request_id,
            "status": "success",
            "output": architect_output,
            "metadata": {"route_key": exchange_req.route_key},
        }

        return map_response("openai.responses", exchange_response)
    except Exception as ex:
        err = {
            "request_id": payload["request_id"],
            "status": "error",
            "error": {
                "code": "agent_execution_error",
                "category": "handler_execution",
                "message": str(ex),
            },
        }
        raise HTTPException(status_code=500, detail=map_response("openai.responses", err)) from ex

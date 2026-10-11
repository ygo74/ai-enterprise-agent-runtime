from ygo74.agent_runtime.domains.contracts import AgentOutput, TextContent
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.handlers.response_validator import validate_response
from ygo74.agent_runtime.routing.dispatcher_impl import DispatcherImpl


def test_handler_response_validator_accepts_success() -> None:
    _ = StandardExchangeRequest(
        request_id="r1", route_key="demo", endpoint_type="openai.responses", input="hi"
    )
    response = StandardExchangeResponse(
        request_id="r1", status="success", output=AgentOutput((TextContent("ok"),))
    )
    validate_response(response)


def test_dispatcher_preserves_a_direct_typed_agent_output() -> None:
    request = StandardExchangeRequest("r1", "demo", "openai.responses", "hi")
    output = AgentOutput((TextContent("answer"),))
    assert (
        DispatcherImpl().dispatch(request, lambda _: lambda incoming: output) is output
    )

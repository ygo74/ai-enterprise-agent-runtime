from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput, TextContent
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
)


def basic_handler(request: StandardExchangeRequest) -> AgentOutput:
    return AgentOutput((TextContent("ok"),))

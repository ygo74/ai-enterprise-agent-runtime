"""Typed output projection facade; request dictionaries remain a separate boundary."""

from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.mapping.anthropic_output import (
    AnthropicOutputProjector,
)
from ygo74.agent_runtime.domains.mapping.chat_completions_output import (
    ChatCompletionsOutputProjector,
)
from ygo74.agent_runtime.domains.mapping.output_normalizer import OutputNormalizer
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProjector,
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mapping.responses_output import (
    ResponsesOutputProjector,
)


class ResponseMapper:
    def __init__(self) -> None:
        self._projectors: dict[OutputProtocol, OutputProjector] = {
            OutputProtocol.CHAT_COMPLETIONS: ChatCompletionsOutputProjector(),
            OutputProtocol.RESPONSES: ResponsesOutputProjector(),
            OutputProtocol.ANTHROPIC_MESSAGES: AnthropicOutputProjector(),
        }
        self._normalizer = OutputNormalizer()

    def project(
        self, result: object, context: ProjectionContext
    ) -> dict[str, JsonValue]:
        return self._projectors[context.protocol].project(
            self._normalizer.normalize(result, request_id=context.request_id or None),
            context,
        )


def map_response(
    endpoint_type: str,
    output: AgentOutput | StandardExchangeResponse,
    *,
    request_id: str = "",
    route_key: str = "",
    model: str | None = None,
    provider_options: dict[str, JsonValue] | None = None,
    request_metadata: dict[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    context = ProjectionContext(
        OutputProtocol(endpoint_type),
        request_id
        or (output.request_id if isinstance(output, StandardExchangeResponse) else ""),
        route_key,
        model,
        provider_options or {},
        request_metadata or {},
    )
    return ResponseMapper().project(output, context)

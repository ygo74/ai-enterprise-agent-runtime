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
    """Represent provider responses with validated fields, separating protocol handling from application logic.
    """
    def __init__(self) -> None:
        """Initialize the instance provider responses with supplied collaborators and configuration.
        """
        self._projectors: dict[OutputProtocol, OutputProjector] = {
            OutputProtocol.CHAT_COMPLETIONS: ChatCompletionsOutputProjector(),
            OutputProtocol.RESPONSES: ResponsesOutputProjector(),
            OutputProtocol.ANTHROPIC_MESSAGES: AnthropicOutputProjector(),
        }
        self._normalizer = OutputNormalizer()

    def project(
        self, result: object, context: ProjectionContext
    ) -> dict[str, JsonValue]:
        """Project provider responses into the response shape required by the selected protocol.

        Args:
            result (object): The operation result to validate, project, or return.
            context (ProjectionContext): The execution context carrying identity and correlated metadata.
        """
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
    """Map response between the source representation and the target contract.

    Args:
        endpoint_type (str): Protocol surface through which the request arrived.
        output (AgentOutput | StandardExchangeResponse): Typed agent output being validated, filtered, or projected.
        request_id (str): Correlation identifier for the incoming request and its response.
        route_key (str): The registered route key identifying the target agent or handler.
        model (str | None): Provider-visible model or agent identifier.
        provider_options (dict[str, JsonValue] | None): Provider-specific options retained for response projection.
        request_metadata (dict[str, JsonValue] | None): Safe request metadata preserved for response projection.
    """
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

"""Inspectable conversion results, without retaining sensitive native payloads."""

from dataclasses import dataclass
from enum import StrEnum

from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent


class ConversionStatus(StrEnum):
    """Names whether framework conversion succeeded, partially succeeded with unsupported content, or excluded the value.
    """
    CONVERTED = "converted"
    EXCLUDED = "excluded"
    UNSUPPORTED = "unsupported"


class ConversionReason(StrEnum):
    """Stable diagnostic categories explaining why a native framework value was excluded or unsupported.
    """
    SUPPORTED = "supported"
    REASONING_NOT_SELECTED = "reasoning_not_selected"
    PROTECTED_REASONING = "protected_reasoning"
    NON_OUTPUT_ROLE = "non_output_role"
    UNKNOWN_CONTENT = "unknown_content"
    INVALID_JSON = "invalid_json"
    MISSING_TOOL_IDENTITY = "missing_tool_identity"
    STRUCTURED_TOOL_RESULT = "structured_tool_result"
    TOOL_ERROR = "tool_error"
    UNSUPPORTED_MEDIA = "unsupported_media"
    INCOMPLETE_USAGE = "incomplete_usage"
    UNKNOWN_FINISH_REASON = "unknown_finish_reason"
    STRUCTURED_RESPONSE_VALUE = "structured_response_value"
    PROVIDER_ERROR = "provider_error"
    UNSUPPORTED_ANNOTATIONS = "unsupported_annotations"


@dataclass(frozen=True, slots=True)
class ConversionDecision:
    """Records one native content item’s conversion status, reason, and safe diagnostic metadata.

    Args:
        content_id (str): Stable identity correlating one content item across start, delta, and end events.
        native_type (str): Framework-native content type being converted.
        status (ConversionStatus): Success, incomplete, or failed outcome for the operation.
        reason (ConversionReason): Reason code or message associated with this decision or failure.
    """
    content_id: str
    native_type: str
    status: ConversionStatus
    reason: ConversionReason


@dataclass(frozen=True, slots=True)
class OutputConversion:
    """Bundles the neutral final result with all conversion decisions made while reading an SDK response.

    Args:
        output (AgentOutput): Typed agent output being validated, filtered, or projected.
        decisions (tuple[ConversionDecision, ...]): Per-content conversion or filtering decisions returned to the caller.
    """
    output: AgentOutput
    decisions: tuple[ConversionDecision, ...]


@dataclass(frozen=True, slots=True)
class UpdateConversion:
    """Bundles typed stream events with the conversion decisions for one SDK update.

    Args:
        events (tuple[AgentStreamEvent, ...]): The ordered typed events that describe the streamed response.
        decisions (tuple[ConversionDecision, ...]): Per-content conversion or filtering decisions returned to the caller.
    """
    events: tuple[AgentStreamEvent, ...]
    decisions: tuple[ConversionDecision, ...]

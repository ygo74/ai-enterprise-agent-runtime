"""Inspectable conversion results, without retaining sensitive native payloads."""

from dataclasses import dataclass
from enum import StrEnum

from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent


class ConversionStatus(StrEnum):
    CONVERTED = "converted"
    EXCLUDED = "excluded"
    UNSUPPORTED = "unsupported"


class ConversionReason(StrEnum):
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
    content_id: str
    native_type: str
    status: ConversionStatus
    reason: ConversionReason


@dataclass(frozen=True, slots=True)
class OutputConversion:
    output: AgentOutput
    decisions: tuple[ConversionDecision, ...]


@dataclass(frozen=True, slots=True)
class UpdateConversion:
    events: tuple[AgentStreamEvent, ...]
    decisions: tuple[ConversionDecision, ...]

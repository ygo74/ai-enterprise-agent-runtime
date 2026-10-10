"""Inspectable conversion decisions, independent of endpoint protocols."""

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


@dataclass(frozen=True, slots=True)
class ConversionDiagnostic:
    """Safe, non-payload diagnostic describing framework content that could not be represented completely.

    Args:
        code (str): Stable error or diagnostic code returned to the caller.
        reason (str): Reason code or message associated with this decision or failure.
    """
    code: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConversionOutcome:
    """Unsupported portions do not discard successfully converted portions.

    Args:
        status (ConversionStatus): Success, incomplete, or failed outcome for the operation.
        events (tuple[AgentStreamEvent, ...]): The ordered typed events that describe the streamed response.
        output (AgentOutput | None): Typed agent output being validated, filtered, or projected.
        diagnostics (tuple[ConversionDiagnostic, ...]): Safe conversion diagnostics collected while processing native content.
    """
    status: ConversionStatus
    events: tuple[AgentStreamEvent, ...] = ()
    output: AgentOutput | None = None
    diagnostics: tuple[ConversionDiagnostic, ...] = ()


class LangChainConversionError(ValueError):
    """An invalid native value or stream lifecycle, not a support limitation."""

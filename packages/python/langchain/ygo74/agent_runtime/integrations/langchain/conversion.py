"""Inspectable conversion decisions, independent of endpoint protocols."""

from dataclasses import dataclass
from enum import StrEnum

from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent


class ConversionStatus(StrEnum):
    CONVERTED = "converted"
    EXCLUDED = "excluded"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ConversionDiagnostic:
    code: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConversionOutcome:
    """Unsupported portions do not discard successfully converted portions."""

    status: ConversionStatus
    events: tuple[AgentStreamEvent, ...] = ()
    output: AgentOutput | None = None
    diagnostics: tuple[ConversionDiagnostic, ...] = ()


class LangChainConversionError(ValueError):
    """An invalid native value or stream lifecycle, not a support limitation."""

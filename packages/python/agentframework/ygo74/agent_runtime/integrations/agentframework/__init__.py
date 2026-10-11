"""Microsoft Agent Framework 1.18 native execution and output integration."""

from .binding import AgentFrameworkSession
from .conversion import (
    ConversionDecision,
    ConversionReason,
    ConversionStatus,
    OutputConversion,
    UpdateConversion,
)
from .output_adapter import AgentFrameworkOutputAdapter
from .stream_adapter import AgentFrameworkStreamAdapter

__all__ = [
    "AgentFrameworkOutputAdapter",
    "AgentFrameworkSession",
    "AgentFrameworkStreamAdapter",
    "ConversionDecision",
    "ConversionReason",
    "ConversionStatus",
    "OutputConversion",
    "UpdateConversion",
]

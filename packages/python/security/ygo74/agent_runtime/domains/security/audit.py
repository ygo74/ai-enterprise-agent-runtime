"""Audit trail of the operations an agent performs.

Every attempt to change external state is recorded, whether it succeeded, was
declined by the caller or failed. The record is deliberately made of identifiers
and outcomes only: no message body, no subject, no recipient list, no credential
ever reaches the audit trail.

That restraint is what makes :class:`LoggingAuditTrail` safe to enable in any
environment, which is the point of shipping it here rather than leaving every
host to write its own.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from ygo74.agent_runtime.domains.security.operations import OperationType, RiskLevel

_LOGGER = logging.getLogger("ygo74.agent_runtime.audit")


class AuditOutcome(StrEnum):
    """How an attempted operation ended."""

    EXECUTED = "EXECUTED"
    DECLINED = "DECLINED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class AuditRecord(BaseModel):
    """One entry of the audit trail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str = Field(min_length=1)
    operation_type: OperationType
    risk_level: RiskLevel
    outcome: AuditOutcome
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    target_id: str | None = None
    confirmation_request_id: str | None = None
    error_type: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class AuditTrail(Protocol):
    """Destination of the audit records."""

    def record(self, entry: AuditRecord) -> None:
        """Persist one audit record."""
        ...


class InMemoryAuditTrail:
    """Keeps audit records in memory, for demonstrations and assertions."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    @property
    def records(self) -> Sequence[AuditRecord]:
        """Every record captured so far."""
        return tuple(self._records)

    def record(self, entry: AuditRecord) -> None:
        """Append one audit record."""
        self._records.append(entry)

    def records_for(self, tool_name: str) -> tuple[AuditRecord, ...]:
        """Records concerning one tool."""
        return tuple(entry for entry in self._records if entry.tool_name == tool_name)

    def clear(self) -> None:
        """Drop every captured record."""
        self._records.clear()


class LoggingAuditTrail:
    """Writes audit records through the standard logging facility.

    Records carry identifiers and outcomes only, so this is safe to enable in
    any environment: no retrieved content can reach the logs through it.
    """

    def __init__(self, delegate: AuditTrail | None = None) -> None:
        self._delegate = delegate

    def record(self, entry: AuditRecord) -> None:
        """Log one audit record and forward it to the delegate, if any."""
        _LOGGER.info(
            "audit tool=%s operation=%s risk=%s outcome=%s user=%s session=%s target=%s error=%s",
            entry.tool_name,
            entry.operation_type.value,
            entry.risk_level.value,
            entry.outcome.value,
            entry.user_id,
            entry.session_id,
            entry.target_id,
            entry.error_type,
        )
        if self._delegate is not None:
            self._delegate.record(entry)

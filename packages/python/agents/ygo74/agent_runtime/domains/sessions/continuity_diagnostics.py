"""Process-local, non-reversible correlation for conversation lifecycle logs."""

import hashlib
import hmac
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4

_salt = uuid4().bytes + uuid4().bytes
_request: ContextVar[str | None] = ContextVar("continuity_request", default=None)


class ContinuationKind(StrEnum):
    """Structural provider handle families, without provider handle contents."""

    ABSENT = "absent"
    STRUCTURED = "structured"
    RESPONSE = "response"
    CONVERSATION = "conversation"
    OPAQUE = "opaque"


@dataclass(frozen=True, slots=True)
class ContinuationReference:
    """Safe provider handle metadata, never the handle itself.

    Args:
        kind: Structural identifier family.
        fingerprint: Process-local keyed digest or absent.
    """

    kind: ContinuationKind
    fingerprint: str | None

    @classmethod
    def of(cls, value: object) -> "ContinuationReference":
        """Classify without serializing structured service handles.

        Args:
            value: Native continuation; only string values are fingerprinted.
        """
        if not isinstance(value, str) or not value:
            kind = ContinuationKind.ABSENT if value is None or value == "" else ContinuationKind.STRUCTURED
            return cls(kind, None)
        kind = ContinuationKind.OPAQUE
        if value.startswith("resp_"):
            kind = ContinuationKind.RESPONSE
        elif value.startswith("conv_"):
            kind = ContinuationKind.CONVERSATION
        return cls(kind, ContinuityDiagnostics.fingerprint(value))


class ContinuityDiagnostics:
    """Reuse standard logging with safe request and identifier correlations."""

    @staticmethod
    def fingerprint(value: str) -> str:
        """Return a keyed process-local digest resistant to guessed identities.

        Args:
            value: Identifier used internally, never emitted in clear.
        """
        return hmac.new(_salt, value.encode("utf-8"), hashlib.sha256).hexdigest()[:24]

    @staticmethod
    @contextmanager
    def request(request_id: str) -> Iterator[None]:
        """Associate logs only during an active request operation.

        Args:
            request_id: Transport correlation, fingerprinted before logging.
        """
        token = _request.set(ContinuityDiagnostics.fingerprint(request_id))
        try:
            yield
        finally:
            _request.reset(token)

    @staticmethod
    def record(logger: logging.Logger, event: str, **fields: str | int | bool | None) -> None:
        """Emit caller-selected structural fields, never arbitrary payloads.

        Args:
            logger: Existing package logger.
            event: Trusted event name.
            fields: Trusted structural metadata only.
        """
        logger.info(event, extra={"request_id": _request.get() or "unscoped", "route": "native",
                                  "request_fingerprint": _request.get(), **fields})

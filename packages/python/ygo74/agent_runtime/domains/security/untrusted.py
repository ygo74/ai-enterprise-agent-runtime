"""Untrusted content primitives.

Anything an agent retrieves - message bodies, page titles, issue descriptions,
web content - is data produced by a third party. It must never be interpreted as
an instruction.

:class:`UntrustedText` makes that property explicit in the type system. The raw
value can only be obtained through :meth:`UntrustedText.expose`, which makes every
place that dereferences untrusted content greppable and reviewable. Its ``repr``
deliberately hides the value, so accidental logging cannot leak content.

The *origin* is a value object rather than an enumeration, and for the same reason
a :class:`~ygo74.agent_runtime.domains.security.permissions.Permission` is: it is
declared by the domain that owns it, never by a central list here. A closed
enumeration would mean that adding an agent required changing this library, and
that every consumer carried the vocabulary of every other.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

_SEPARATOR = ":"


@dataclass(frozen=True, slots=True, order=True)
class UntrustedOrigin:
    """Where a piece of untrusted content came from.

    Non-sensitive by construction: a domain and a kind, both safe to log. It says
    *what sort of thing* the content is, never what it contains.

    Attributes:
        domain: The system the content came from - ``"mail"``, ``"wiki"``.
        kind: What part of it - ``"body"``, ``"page_title"``.
    """

    domain: str
    kind: str

    def __post_init__(self) -> None:
        """Reject an origin that could not be written as ``domain:kind``."""
        for part in (self.domain, self.kind):
            if not part or _SEPARATOR in part:
                raise ValueError(f"invalid untrusted origin part {part!r}")

    @property
    def value(self) -> str:
        """Canonical text form, as used in logs and audit records."""
        return f"{self.domain}{_SEPARATOR}{self.kind}"

    def __str__(self) -> str:
        """Return the canonical text form."""
        return self.value


class UntrustedText(BaseModel):
    """Text produced outside the trust boundary of the application.

    The payload is excluded from ``repr``/``str`` so that logging a model that
    embeds untrusted content cannot leak it. Read the payload through
    :meth:`expose`, which documents the caller's intent at the call site.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    origin: UntrustedOrigin
    payload: str = Field(repr=False)

    @property
    def length(self) -> int:
        """Length of the underlying text, safe to log."""
        return len(self.payload)

    @property
    def is_empty(self) -> bool:
        """Whether the underlying text holds no visible character."""
        return not self.payload.strip()

    def expose(self) -> str:
        """Return the raw untrusted text.

        Callers must treat the result as data. It may only be embedded in a
        prompt through a builder that delimits and labels untrusted sections.
        """
        return self.payload

    def __repr__(self) -> str:
        """Redacted representation: never reveals the untrusted payload."""
        return f"UntrustedText(origin={self.origin.value!r}, length={self.length})"

    def __str__(self) -> str:
        """Redacted representation, so f-strings cannot leak the payload."""
        return self.__repr__()


def untrusted(value: str, origin: UntrustedOrigin) -> UntrustedText:
    """Wrap a raw string coming from outside the trust boundary."""
    return UntrustedText(origin=origin, payload=value)

"""Transport headers a handler is allowed to see.

A request carries more than its body. LibreChat, and most OpenAI-compatible
clients, identify a conversation with a header rather than with a field of the
JSON payload, because the OpenAI schema has no place for one. A handler keeping
per-conversation state therefore cannot find it: every turn looks like a first
turn, and a conversation that should have continued starts again.

Forwarding every header would fix that and leak a credential in the same move -
``authorization`` and ``x-api-key`` are headers too, and the uniform payload
reaches handler code, logs, and, for an agent, prompts. So forwarding is an
allowlist, and it fails closed in both directions: a header nobody listed never
reaches a handler, and a header carrying a credential is refused when the
endpoints are registered rather than quietly dropped at runtime.

What a handler receives is placed in ``metadata``:

* ``metadata["headers"]`` - the allowlisted headers, lowercased;
* ``metadata["conversation_id"]`` - the conversation header, promoted to a
  stable key so a handler does not have to know which header a deployment uses.

Both are *replaced*, never merged with what the body sent: a caller must not be
able to forge transport data by writing it into the payload.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

HEADERS_KEY = "headers"
CONVERSATION_KEY = "conversation_id"

DEFAULT_CONVERSATION_HEADER = "x-conversation-id"

# Correlation identifiers a handler routinely needs, and nothing else. Anything
# further is a deployment decision, made explicit through ``forwarded_headers``.
DEFAULT_FORWARDED_HEADERS: tuple[str, ...] = (
    DEFAULT_CONVERSATION_HEADER,
    "x-correlation-id",
    "x-request-id",
)

# Headers that carry a credential by definition. The authenticator chain adds
# whichever header it actually reads, so a renamed API key header is refused too.
CREDENTIAL_HEADERS: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
    }
)


@dataclass(frozen=True, slots=True)
class RequestHeaderForwarder:
    """Copies the headers a deployment declared safe into the uniform payload."""

    forwarded: tuple[str, ...]
    conversation_header: str = DEFAULT_CONVERSATION_HEADER

    @classmethod
    def create(
        cls,
        *,
        forwarded: Iterable[str] | None = None,
        conversation_header: str = DEFAULT_CONVERSATION_HEADER,
        credential_headers: Iterable[str] = (),
    ) -> RequestHeaderForwarder:
        """Build a forwarder, refusing one that would disclose a credential.

        Raising here rather than redacting later makes a misconfiguration a
        startup failure: a deployment that would have leaked a token never
        serves a request.
        """
        conversation = _name(conversation_header)
        names = _names(DEFAULT_FORWARDED_HEADERS if forwarded is None else forwarded)
        if conversation:
            names = names if conversation in names else (*names, conversation)

        forbidden = CREDENTIAL_HEADERS.union(_names(credential_headers))
        leaking = sorted(name for name in names if name in forbidden)
        if leaking:
            raise ValueError(f"refusing to forward credential headers: {', '.join(leaking)}")

        return cls(forwarded=names, conversation_header=conversation)

    def apply(self, metadata: Mapping[str, Any], headers: Mapping[str, Any] | None) -> dict[str, Any]:
        """Return the metadata a handler receives, transport data included."""
        enriched = dict(metadata)
        forwarded = self._collect(headers)
        enriched[HEADERS_KEY] = forwarded

        conversation = self._conversation(metadata, forwarded)
        if conversation:
            enriched[CONVERSATION_KEY] = conversation
        return enriched

    def _collect(self, headers: Mapping[str, Any] | None) -> dict[str, str]:
        """Read the allowlisted headers the request actually carried."""
        if headers is None:
            return {}
        return {name: value for name in self.forwarded if (value := _value(headers, name))}

    def _conversation(self, metadata: Mapping[str, Any], forwarded: Mapping[str, str]) -> str:
        """Resolve which conversation this request continues.

        An explicit ``conversation_id`` in the body wins: a client that named a
        conversation in the payload meant that one, whatever a proxy added.
        """
        stated = metadata.get(CONVERSATION_KEY)
        if isinstance(stated, str) and stated.strip():
            return stated.strip()
        return forwarded.get(self.conversation_header, "")


def _names(values: Iterable[str]) -> tuple[str, ...]:
    """Return lowercased header names, deduplicated and in order."""
    return tuple(dict.fromkeys(name for value in values if (name := _name(value))))


def _name(value: str) -> str:
    """Return a comparable header name, or nothing at all."""
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _value(headers: Mapping[str, Any], name: str) -> str:
    """Read one header, whatever mapping the transport provided.

    A framework hands over a case-insensitive mapping, a test often hands over a
    plain dict. Both are read the same way so behaviour does not depend on how
    the request was produced.
    """
    getter = getattr(headers, "get", None)
    if callable(getter) and (value := _text(getter(name))):
        return value
    return _scan(headers, name)


def _scan(headers: Mapping[str, Any], name: str) -> str:
    """Find a header in a mapping whose keys are not lowercased."""
    items = getattr(headers, "items", None)
    if not callable(items):
        return ""
    for key, value in items():
        if isinstance(key, str) and key.lower() == name and (text := _text(value)):
            return text
    return ""


def _text(value: object) -> str:
    """Return a non-empty header value, trimmed."""
    if not isinstance(value, str):
        return ""
    return value.strip()

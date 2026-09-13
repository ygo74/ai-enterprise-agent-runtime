"""Reading a transport payload into a turn, and a reply back out.

An endpoint hands a handler a loosely-typed mapping: that is what a transport
boundary is. This module is the seam that crosses it, and it has one rule - it is
the **only** place allowed to see that shape. Everything it hands onwards is a
typed model.

Nothing here knows which agent it serves, which framework answers, or which
protocol carried the question. That is what lets two different agents be served
identically and compared honestly: identity, conversation routing and payload
normalisation are written once rather than once per agent.

The keys read here are the ones
:mod:`ygo74.agent_runtime.domains.endpoints.header_forwarding` writes, and they
are imported from it rather than restated, so the producer and the consumer of a
payload cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.contracts.contract_errors import EmptyRequestError
from ygo74.agent_runtime.domains.contracts.conversation import AgentReply, ConversationTurn
from ygo74.agent_runtime.domains.endpoints.header_forwarding import (
    CONVERSATION_KEY,
    DEFAULT_CONVERSATION_HEADER,
    HEADERS_KEY,
)

DEFAULT_CONVERSATION = "default"

_INPUT = "input"
_METADATA = "metadata"
_AUTH_CONTEXT = "auth_context"
_ROLE = "role"
_CONTENT = "content"
_USER = "user"
_TEXT = "text"
_REQUEST_ID = "request_id"
_ROUTE_KEY = "route_key"


class ConversationPayloadReader:
    """Reads one request into the typed turn an agent works with.

    Args:
        require_email: Whether a caller without an address is refused. Passed
            through to :meth:`AgentPrincipal.from_auth_context`, so an agent that
            addresses its subject by e-mail keeps that guarantee and one whose
            accounts are not e-mail addresses is not made to invent one.
        default_conversation: Which conversation a request that names none
            continues.
    """

    def __init__(
        self,
        *,
        require_email: bool = True,
        default_conversation: str = DEFAULT_CONVERSATION,
    ) -> None:
        self._require_email = require_email
        self._default_conversation = default_conversation

    def to_turn(self, payload: Mapping[str, Any]) -> ConversationTurn:
        """Read a request into the typed model the agent works with.

        The principal comes from ``auth_context``, which the endpoint populated
        from a verified token or an API key. It is never taken from the body: a
        caller must not be able to name themselves.
        """
        return ConversationTurn(
            principal=AgentPrincipal.from_auth_context(
                _mapping(payload.get(_AUTH_CONTEXT)),
                require_email=self._require_email,
            ),
            conversation_id=self.conversation_of(payload),
            message=latest_message(payload.get(_INPUT)),
        )

    def conversation_of(self, payload: Mapping[str, Any]) -> str:
        """Find which conversation this request continues.

        A chat client sends its conversation identifier as a header, because the
        OpenAI schema has no field for one. The endpoint forwards it into
        ``metadata``, both under a stable key and among the headers it carried;
        both are read so a handler does not depend on which of the two a given
        runtime version populates.

        A stable default is used when neither is present. Falling back is safe:
        the identifier only selects state *within* an authenticated subject, so
        at worst one caller's turns share a conversation, never two callers'.
        """
        metadata = _mapping(payload.get(_METADATA))
        headers = _mapping(metadata.get(HEADERS_KEY))
        for source, key in ((metadata, CONVERSATION_KEY), (headers, DEFAULT_CONVERSATION_HEADER)):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return self._default_conversation


class AgentReplyRenderer:
    """Renders a reply in the exchange shape the endpoint maps to a protocol."""

    def to_payload(self, payload: Mapping[str, Any], reply: AgentReply) -> dict[str, Any]:
        """Render one reply against the request it answers."""
        return {
            _REQUEST_ID: str(payload.get(_REQUEST_ID, "")),
            "status": "success",
            "output": reply.text,
            _METADATA: {
                _ROUTE_KEY: str(payload.get(_ROUTE_KEY, "")),
                "pending_confirmations": list(reply.pending_confirmations),
            },
        }


def latest_message(value: object) -> str:
    """Return what the person just wrote.

    The history is re-sent in full on every request, so only the last user turn
    is new. Everything before it is already in the agent's own session, and
    replaying it would duplicate the conversation.

    Raises:
        EmptyRequestError: the request carried no user message at all.
    """
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        for item in reversed(value):
            if not isinstance(item, Mapping) or item.get(_ROLE) != _USER:
                continue
            if text := _content_text(item.get(_CONTENT)):
                return text
    raise EmptyRequestError


def _content_text(content: object) -> str:
    """Flatten a message content, string or content-part list."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = [str(part.get(_TEXT, "")).strip() for part in content if isinstance(part, Mapping) and part.get(_TEXT)]
    return "\n".join(part for part in parts if part)


def _mapping(value: object) -> Mapping[str, Any]:
    """Return a mapping, whatever the transport actually sent."""
    return value if isinstance(value, Mapping) else {}

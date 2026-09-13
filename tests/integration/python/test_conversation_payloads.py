"""Tests of the seam between a transport payload and a typed conversation turn.

The security-relevant property is that the caller is read from ``auth_context``
and never from the body: a request naming a subject must not become that subject.
"""

from __future__ import annotations

from typing import Any

import pytest
from ygo74.agent_runtime.domains.auth.agent_principal import PrincipalError
from ygo74.agent_runtime.domains.contracts.contract_errors import EmptyRequestError
from ygo74.agent_runtime.domains.contracts.conversation import (
    AgentReply,
    ConversationTurn,
)
from ygo74.agent_runtime.domains.endpoints.conversation_payloads import (
    DEFAULT_CONVERSATION,
    AgentReplyRenderer,
    ConversationPayloadReader,
    latest_message,
)


def payload(**overrides: Any) -> dict[str, Any]:
    """Build the shape ``add_ai_endpoints`` hands to an entrypoint."""
    body: dict[str, Any] = {
        "request_id": "req-1",
        "route_key": "mail-agent",
        "input": [{"role": "user", "content": "what is waiting for me?"}],
        "metadata": {},
        "auth_context": {
            "authType": "jwt",
            "userId": "3f9a-user",
            "identity": {"subject": "3f9a-user", "email": "ada@example.com", "name": "Ada"},
            "roles": ["agent-user"],
        },
    }
    body.update(overrides)
    return body


def test_it_reads_the_caller_the_conversation_and_the_message() -> None:
    turn = ConversationPayloadReader().to_turn(payload())

    assert turn.principal.subject == "3f9a-user"
    assert turn.conversation_id == DEFAULT_CONVERSATION
    assert turn.message == "what is waiting for me?"


def test_the_state_key_puts_the_authenticated_subject_first() -> None:
    turn = ConversationPayloadReader().to_turn(payload(metadata={"conversation_id": "conv-9"}))

    assert turn.key == ("3f9a-user", "conv-9")


def test_the_conversation_is_read_from_the_stable_metadata_key() -> None:
    reader = ConversationPayloadReader()

    assert reader.conversation_of(payload(metadata={"conversation_id": " conv-7 "})) == "conv-7"


def test_the_conversation_is_also_read_from_the_forwarded_header() -> None:
    reader = ConversationPayloadReader()
    body = payload(metadata={"headers": {"x-conversation-id": "conv-8"}})

    assert reader.conversation_of(body) == "conv-8"


def test_the_stable_key_wins_over_the_header() -> None:
    reader = ConversationPayloadReader()
    body = payload(metadata={"conversation_id": "conv-7", "headers": {"x-conversation-id": "conv-8"}})

    assert reader.conversation_of(body) == "conv-7"


def test_a_request_naming_no_conversation_continues_the_default() -> None:
    reader = ConversationPayloadReader(default_conversation="solo")

    assert reader.conversation_of(payload(metadata={"conversation_id": "   "})) == "solo"


def test_a_request_without_an_authenticated_caller_is_refused() -> None:
    """The subject is never taken from the body, so there is nothing to fall back on."""
    with pytest.raises(PrincipalError, match="no authenticated caller"):
        ConversationPayloadReader().to_turn(payload(auth_context=None))


def test_an_agent_that_does_not_address_by_email_accepts_a_caller_without_one() -> None:
    body = payload(
        auth_context={"userId": "wiki-user", "identity": {"subject": "wiki-user"}, "roles": []},
    )

    turn = ConversationPayloadReader(require_email=False).to_turn(body)

    assert turn.principal.subject == "wiki-user"
    assert turn.principal.email == ""


def test_only_the_last_user_message_is_read() -> None:
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "an answer"},
        {"role": "user", "content": "second"},
    ]

    assert latest_message(history) == "second"


def test_a_plain_string_input_is_accepted() -> None:
    assert latest_message("  just this  ") == "just this"


def test_content_parts_are_flattened() -> None:
    history = [{"role": "user", "content": [{"text": "one"}, {"text": "two"}]}]

    assert latest_message(history) == "one\ntwo"


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", [], [{"role": "assistant", "content": "only an answer"}]],
)
def test_a_request_carrying_no_user_message_is_reported(value: object) -> None:
    with pytest.raises(EmptyRequestError):
        latest_message(value)


def test_a_reply_is_rendered_against_the_request_it_answers() -> None:
    rendered = AgentReplyRenderer().to_payload(payload(), AgentReply("here you are"))

    assert rendered["request_id"] == "req-1"
    assert rendered["status"] == "success"
    assert rendered["output"] == "here you are"
    assert rendered["metadata"]["route_key"] == "mail-agent"
    assert rendered["metadata"]["pending_confirmations"] == []


def test_a_reply_reports_what_it_left_waiting() -> None:
    reply = AgentReply("nothing was changed", ("cfm-abc123",))

    rendered = AgentReplyRenderer().to_payload(payload(), reply)

    assert reply.awaits_confirmation
    assert rendered["metadata"]["pending_confirmations"] == ["cfm-abc123"]


def test_a_reply_with_nothing_pending_does_not_claim_success_of_a_write() -> None:
    assert not AgentReply("done").awaits_confirmation


def test_a_turn_is_immutable() -> None:
    turn: ConversationTurn = ConversationPayloadReader().to_turn(payload())

    with pytest.raises(AttributeError):
        turn.conversation_id = "somebody-elses"  # type: ignore[misc]

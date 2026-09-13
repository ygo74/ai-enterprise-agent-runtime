"""Tests of the manifest contract and of the capability registry.

The invariant worth protecting is that a capability cannot advertise one name
while carrying the security posture of another: that mismatch is how an operation
ends up both never asked about and always refused.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel
from ygo74.agent_runtime.domains.contracts.capability_registry import (
    SkillDescriptor,
    SkillRegistry,
)
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.user_context import UserContext

SEND = Permission("mail", "send")
READ = Permission("mail", "read")


class _Arguments(BaseModel):
    subject: str = ""


class _Result(BaseModel):
    text: str = ""


def _operation(
    tool_name: str,
    *,
    operation_type: OperationType = OperationType.WRITE,
    permission: Permission = SEND,
) -> ToolOperationDescriptor:
    return ToolOperationDescriptor(
        tool_name=tool_name,
        operation_type=operation_type,
        risk_level=RiskLevel.HIGH,
        required_permission=permission,
        confirmation_required_by_default=True,
    )


def _manifest(tool_name: str = "send_mail", **overrides: object) -> SkillManifest:
    fields: dict[str, object] = {
        "tool_name": tool_name,
        "implementation": "send",
        "description": "Sends a message that has been drafted.",
        "operation": _operation(tool_name),
    }
    fields.update(overrides)
    return SkillManifest(**fields)  # type: ignore[arg-type]


async def _invoke(payload: BaseModel, user: UserContext) -> BaseModel:
    del payload, user
    return _Result(text="done")


def test_a_manifest_carries_what_configuration_declares() -> None:
    manifest = _manifest()

    assert manifest.tool_name == "send_mail"
    assert manifest.operation.is_write
    assert not manifest.is_reasoning


def test_a_manifest_with_a_prompt_drives_a_model() -> None:
    assert _manifest(prompt="Summarise the thread.").is_reasoning


def test_a_manifest_declaring_the_operation_of_another_tool_is_refused() -> None:
    with pytest.raises(ValueError, match="declares the operation of"):
        _manifest("send_mail", operation=_operation("archive_mail"))


def test_an_agent_manifest_finds_a_declared_skill() -> None:
    agent = AgentManifest(
        name="Mail Agent",
        description="Works a mailbox.",
        instructions="Be precise.",
        skills=(_manifest(), _manifest("search_mail")),
    )

    assert agent.skill("search_mail").tool_name == "search_mail"


def test_an_agent_manifest_refuses_a_skill_it_does_not_declare() -> None:
    agent = AgentManifest(
        name="Mail Agent",
        description="Works a mailbox.",
        instructions="Be precise.",
        skills=(_manifest(),),
    )

    with pytest.raises(KeyError, match="declares no skill named"):
        agent.skill("delete_everything")


def test_a_descriptor_is_bound_from_a_manifest() -> None:
    descriptor = SkillDescriptor.from_manifest(_manifest(), _Arguments, _invoke)

    assert descriptor.tool_name == "send_mail"
    assert descriptor.input_model is _Arguments
    assert descriptor.operation.required_permission == SEND


def test_a_descriptor_whose_name_does_not_match_its_operation_is_refused() -> None:
    with pytest.raises(ValueError, match="declares the operation of"):
        SkillDescriptor(
            tool_name="send_mail",
            description="Sends a message.",
            input_model=_Arguments,
            operation=_operation("archive_mail"),
            invoke=_invoke,
        )


def test_a_registry_finds_a_capability_by_name() -> None:
    registry = SkillRegistry([SkillDescriptor.from_manifest(_manifest(), _Arguments, _invoke)])

    assert registry.skill("send_mail").description.startswith("Sends")


def test_a_registry_refuses_a_capability_it_does_not_hold() -> None:
    registry = SkillRegistry([])

    with pytest.raises(KeyError, match="no skill named"):
        registry.skill("send_mail")


def test_a_registry_reports_only_the_capabilities_that_change_state() -> None:
    write = SkillDescriptor.from_manifest(_manifest(), _Arguments, _invoke)
    read = SkillDescriptor.from_manifest(
        _manifest("search_mail", operation=_operation("search_mail", operation_type=OperationType.READ, permission=READ)),
        _Arguments,
        _invoke,
    )

    registry = SkillRegistry([write, read])

    assert [descriptor.tool_name for descriptor in registry.write_skills()] == ["send_mail"]


def test_a_capability_is_invoked_with_its_payload_and_its_caller() -> None:
    """Driven with ``asyncio.run`` rather than a plugin: this repository declares
    no async test framework, and a test that needed one would pass here and fail
    in its own CI."""
    descriptor = SkillDescriptor.from_manifest(_manifest(), _Arguments, _invoke)
    user = UserContext(user_id="alice", session_id="s-1", permissions=frozenset({SEND}))

    result = asyncio.run(descriptor.invoke(_Arguments(subject="hello"), user))

    assert isinstance(result, _Result)
    assert result.text == "done"

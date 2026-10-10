"""Contract tests for framework-neutral native registration."""

from datetime import datetime, timezone

import pytest
from ygo74.agent_runtime.domains.contracts.agent_definition import AgentDefinition
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)
from ygo74.agent_runtime.domains.security.operations import ToolOperationDescriptor
from ygo74.agent_runtime.domains.security.permissions import Permission


def descriptor():
    return AgentDescriptor(
        agent_id="native", route_key="native", display_name="Native",
        description="A native agent", version="1",
        owner="lab", created_at_utc=datetime.now(timezone.utc), capabilities=AgentCapabilitySet(streaming=True),
    )


def test_native_definition_needs_no_registry_or_skills():
    definition = AgentDefinition(descriptor(), "package.agent:create")
    assert definition.require_email is False
    assert definition.tools == ()


def test_factory_is_a_trusted_export_not_a_file_path():
    with pytest.raises(ValueError, match="export"):
        AgentDefinition(descriptor(), "..\\user_input.py")


def test_tools_require_an_enforceable_control_point():
    with pytest.raises(ValueError, match="control"):
        AgentDefinition(descriptor(), "package.agent:create", tools=(
            ToolOperationDescriptor(tool_name="send", operation_type="WRITE", risk_level="HIGH",
                                    required_permission=Permission("native", "send"), confirmation_required_by_default=True),
        ))

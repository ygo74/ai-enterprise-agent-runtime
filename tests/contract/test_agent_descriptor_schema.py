import json
from pathlib import Path

SCHEMA_PATH = Path("specs/001-openai-endpoint-exposure/contracts/agent-descriptor-v1.schema.json")


def _schema() -> dict:
    assert SCHEMA_PATH.exists()
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_agent_descriptor_schema_declares_required_identity_fields() -> None:
    schema = _schema()
    assert set(schema["required"]) == {
        "agentId",
        "routeKey",
        "displayName",
        "description",
        "version",
        "owner",
        "createdAtUtc",
        "capabilities",
    }


def test_agent_descriptor_schema_constrains_agent_id_for_path_and_model_use() -> None:
    agent_id = _schema()["properties"]["agentId"]
    assert agent_id["pattern"] == "^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    assert agent_id["maxLength"] == 128


def test_agent_descriptor_schema_defines_visibility_and_size_unit_enums() -> None:
    schema = _schema()
    assert schema["properties"]["discoveryVisibility"]["enum"] == ["listed", "hidden"]

    capabilities = schema["$defs"]["agentCapabilitySet"]
    assert capabilities["properties"]["sizeUnit"]["enum"] == ["tokens", "characters", "bytes"]
    assert capabilities["dependentRequired"] == {
        "maxInputSize": ["sizeUnit"],
        "maxOutputSize": ["sizeUnit"],
    }


def test_agent_descriptor_model_round_trips_through_the_schema_shape() -> None:
    from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor

    payload = {
        "agentId": "support-agent",
        "routeKey": "support",
        "displayName": "Support Agent",
        "description": "Answers support questions.",
        "version": "1.0.0",
        "owner": "platform-team",
        "createdAtUtc": "2026-08-16T00:00:00Z",
        "capabilities": {
            "streaming": True,
            "inputModalities": ["text"],
            "outputModalities": ["text"],
            "sizeUnit": "tokens",
            "maxInputSize": 8000,
        },
        "skills": [
            {"skillId": "faq", "name": "FAQ", "description": "Answers frequent questions."},
        ],
        "securitySchemes": ["jwt"],
        "discoveryVisibility": "listed",
    }

    descriptor = AgentDescriptor.from_dict(payload)
    rendered = descriptor.to_dict()

    assert rendered["agentId"] == "support-agent"
    assert rendered["createdAtUtc"] == "2026-08-16T00:00:00Z"
    assert rendered["capabilities"]["sizeUnit"] == "tokens"
    assert rendered["capabilities"]["maxInputSize"] == 8000
    assert rendered["skills"][0]["skillId"] == "faq"
    assert set(rendered).issubset(set(_schema()["properties"]))

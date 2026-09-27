"""The distributed manifest schemas stay aligned with their typed inputs."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import BaseModel
from ygo74.agent_runtime.domains.configuration.manifest_inputs import (
    AgentManifestInput,
    SkillManifestInput,
)
from ygo74.agent_runtime.domains.configuration.manifest_schemas import ManifestSchemas


@pytest.mark.parametrize(
    ("read_schema", "input_model", "schema_id"),
    [
        (
            ManifestSchemas.agent,
            AgentManifestInput,
            "urn:ygo74:agent-runtime:agent-manifest:1",
        ),
        (
            ManifestSchemas.skill,
            SkillManifestInput,
            "urn:ygo74:agent-runtime:skill-manifest:1",
        ),
    ],
)
def test_packaged_schema_matches_its_typed_input(
    read_schema: Callable[[], str],
    input_model: type[BaseModel],
    schema_id: str,
) -> None:
    schema = json.loads(read_schema())

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == schema_id
    del schema["$schema"]
    del schema["$id"]
    assert schema == input_model.model_json_schema()

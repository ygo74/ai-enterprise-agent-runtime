"""The agent MCP adapter keeps its inputs and outputs provider-neutral."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from discovery_fixtures import make_descriptor
from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from ygo74.agent_runtime.domains.configuration.agent_http_configuration import (
    AgentHttpSettingsBuilder,
)
from ygo74.agent_runtime.domains.configuration.manifest_inputs import AgentManifestInput
from ygo74.agent_runtime.domains.contracts import AgentOutput, TextContent
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.contracts.invocation_context import (
    AgentInvocationContextScope,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import HostingFactory

API_KEY = "agent-endpoint-test-key"


@pytest.mark.asyncio
async def test_mcp_operation_uses_verified_identity_and_returns_typed_exchange() -> (
    None
):
    """The tool schema excludes identity and the call preserves the typed reply."""
    captured_payloads: list[dict[str, Any]] = []
    captured_contexts = []

    async def invoke(payload: dict[str, Any]) -> StandardExchangeResponse:
        """Record the normalized call and return one conversation result."""
        captured_payloads.append(payload)
        captured_contexts.append(AgentInvocationContextScope.current())
        return StandardExchangeResponse(
            request_id=payload["request_id"],
            status="success",
            output=AgentOutput((TextContent("Hello from the agent."),)),
            metadata={"pending_confirmations": ["confirm-send-1"]},
        )

    manifest = AgentManifestInput.model_validate(
        {
            "name": "mail-agent",
            "description": "Mail service.",
            "skills": ["search"],
            "http": {
                "endpoints": ["mcp"],
                "security": {
                    "mode": "api_key",
                    "api_key": {
                        "value": "${MAIL_AGENT_API_KEY}",
                        "user": {
                            "subject": "caller-1",
                            "email": "caller@example.test",
                        },
                    },
                },
            },
        }
    )
    assert manifest.http is not None
    settings = AgentHttpSettingsBuilder({"MAIL_AGENT_API_KEY": API_KEY}).build(
        manifest.http
    )
    app = FastAPI()

    @app.get("/health/ready")
    async def readiness() -> dict[str, bool]:
        """Keep the worker readiness route outside the mounted MCP sub-app."""
        return {"ready": True}

    @app.get("/plain")
    async def unprotected() -> dict[str, bool]:
        """Keep unrelated application routes outside MCP authentication."""
        return {"protected": False}

    HostingFactory(app).add_agent(
        invoke, make_descriptor("mail-agent")
    ).add_http_settings(settings).register()

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://agent.test"
        ) as public_client:
            assert (await public_client.get("/health/ready")).json() == {"ready": True}
            assert (await public_client.get("/plain")).json() == {"protected": False}
        async with (
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://agent.test",
                headers={"x-api-key": API_KEY},
            ) as http_client,
            streamable_http_client(
                "http://agent.test/mcp", http_client=http_client
            ) as (read_stream, write_stream, _get_session_id),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            result = await session.call_tool(
                "invoke_agent",
                {"message": "Summarize my inbox.", "conversation_id": "work"},
            )

    assert len(listed.tools) == 1
    tool = listed.tools[0]
    assert tool.name == "invoke_agent"
    assert set(tool.inputSchema["properties"]) == {"message", "conversation_id"}
    assert tool.inputSchema["required"] == ["message"]
    assert result.isError is False
    assert result.structuredContent == {
        "status": "success",
        "conversation_id": "work",
        "output": {
            "type": "agent_output",
            "value": {
                "contents": [
                    {
                        "type": "text",
                        "value": {"text": "Hello from the agent.", "annotations": []},
                    }
                ],
                "usage": None,
                "termination": {
                    "status": "success",
                    "reason": None,
                    "error": None,
                },
            },
        },
        "metadata": {"pending_confirmations": ["confirm-send-1"]},
    }
    assert captured_payloads[0]["input"] == "Summarize my inbox."
    assert captured_payloads[0]["metadata"]["conversation_id"] == "work"
    assert captured_payloads[0]["auth_context"]["userId"] == "caller-1"
    assert captured_contexts[0] is not None
    assert captured_contexts[0].principal.subject == "caller-1"

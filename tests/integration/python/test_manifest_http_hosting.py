"""Manifest HTTP settings feed the existing FastAPI host and auth pipeline."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import redis
from discovery_fixtures import make_descriptor
from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtAuthenticator
from ygo74.agent_runtime.domains.configuration.agent_http_configuration import (
    AgentHttpSettingsBuilder,
)
from ygo74.agent_runtime.domains.configuration.manifest_inputs import AgentManifestInput
from ygo74.agent_runtime.domains.contracts import AgentOutput, TextContent
from ygo74.agent_runtime.domains.contracts.http_configuration import HttpEndpoint
from ygo74.agent_runtime.domains.endpoints.hosting_factory import HostingFactory


def _manifest() -> AgentManifestInput:
    """Return an agent whose manifest enables only authenticated Chat Completions."""
    return AgentManifestInput.model_validate(
        {
            "name": "mail-agent",
            "description": "Mail service.",
            "skills": ["search"],
            "http": {
                "endpoints": ["chat_completions"],
                "security": {
                    "mode": "api_key",
                    "api_key": {
                        "value": "${MAIL_HTTP_API_KEY}",
                        "header_name": "X-API-Key",
                        "user": {
                            "subject": "mail-service",
                            "email": "mail@example.test",
                        },
                    },
                },
            },
        }
    )


async def _invoke(payload: dict[str, Any]) -> AgentOutput:
    """Return the verified caller identity for this integration scenario."""
    return AgentOutput(
        (TextContent(json.dumps(payload["auth_context"])),)
    )


async def _post(
    app: FastAPI,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Send a request through the in-process ASGI application."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        return await client.post(path, json=payload, headers=headers)


def test_manifest_settings_register_only_selected_authenticated_route() -> None:
    """An agent manifest drives endpoint selection and the existing identity projection."""
    source = _manifest()
    assert source.http is not None
    app = FastAPI()
    settings = AgentHttpSettingsBuilder(
        {"MAIL_HTTP_API_KEY": "resolved-mail-key"}
    ).build(source.http)
    HostingFactory(app).add_agent(_invoke, make_descriptor("mail-agent")).add_http_settings(
        settings
    ).register()

    missing_key = asyncio.run(
        _post(app, "/v1/chat/completions", {"messages": [{"role": "user", "content": "hi"}]})
    )
    accepted = asyncio.run(
        _post(
            app,
            "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "hi"}]},
            {"X-API-Key": "resolved-mail-key"},
        )
    )
    disabled = asyncio.run(
        _post(app, "/v1/responses", {"input": "hi"}, {"X-API-Key": "resolved-mail-key"})
    )

    assert missing_key.status_code == 401
    assert accepted.status_code == 200
    assert '"userId": "mail-service"' in accepted.json()["choices"][0]["message"]["content"]
    assert disabled.status_code == 404


def test_manifest_resolves_mcp_resource_url_for_jwt_endpoint() -> None:
    """The MCP resource URL is resolved only after the manifest is validated."""
    manifest = AgentManifestInput.model_validate(
        {
            "name": "mail-agent",
            "description": "Mail service.",
            "skills": ["search"],
            "http": {
                "endpoints": ["mcp"],
                "mcp": {"resource_url": "${MAIL_AGENT_MCP_RESOURCE_URL}"},
                "security": {
                    "mode": "jwt",
                    "jwt": {
                        "issuer": "https://identity.example.test/issuer",
                        "secret": "${MAIL_AGENT_JWT_SECRET}",
                        "audience": "mail-agent",
                    },
                },
            },
        }
    )

    assert manifest.http is not None
    settings = AgentHttpSettingsBuilder(
        {
            "MAIL_AGENT_MCP_RESOURCE_URL": "https://mail.example.test/mcp",
            "MAIL_AGENT_JWT_SECRET": "test-signing-secret",
        }
    ).build(manifest.http)

    assert settings.endpoints == (HttpEndpoint.MCP,)
    assert settings.mcp_resource_url == "https://mail.example.test/mcp"


def test_manifest_requires_mcp_resource_url_for_jwt_endpoint() -> None:
    """A JWT-protected MCP endpoint cannot start without OAuth resource metadata."""
    with pytest.raises(ValueError, match="resource_url"):
        AgentManifestInput.model_validate(
            {
                "name": "mail-agent",
                "description": "Mail service.",
                "skills": ["search"],
                "http": {
                    "endpoints": ["mcp"],
                    "security": {
                        "mode": "jwt",
                        "jwt": {
                            "issuer": "https://identity.example.test/issuer",
                            "secret": "${MAIL_AGENT_JWT_SECRET}",
                            "audience": "mail-agent",
                        },
                    },
                },
            }
        )


def test_manifest_mcp_api_key_endpoint_does_not_require_resource_url() -> None:
    """API-key MCP does not advertise OAuth protected-resource metadata."""
    manifest = AgentManifestInput.model_validate(
        {
            "name": "wiki-agent",
            "description": "Wiki service.",
            "skills": ["search"],
            "http": {
                "endpoints": ["mcp"],
                "security": {
                    "mode": "api_key",
                    "api_key": {
                        "value": "${WIKI_AGENT_API_KEY}",
                        "user": {"subject": "wiki-service"},
                    },
                },
            },
        }
    )

    assert manifest.http is not None
    settings = AgentHttpSettingsBuilder(
        {"WIKI_AGENT_API_KEY": "test-api-key"}
    ).build(manifest.http)

    assert settings.endpoints == (HttpEndpoint.MCP,)
    assert settings.mcp_resource_url is None


def test_manifest_http_resources_close_after_custom_fastapi_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manifest-owned JWT and Redis resources close after an app-owned lifespan."""
    closed: list[JwtAuthenticator] = []
    closed_redis_clients: list[redis.Redis] = []
    original_lifespan_exited: list[bool] = []
    closed_after_lifespan: list[bool] = []
    redis_closed_after_lifespan: list[bool] = []

    def close(authenticator: JwtAuthenticator) -> None:
        """Record closure of the JWT authenticator owned by manifest settings."""
        closed.append(authenticator)
        closed_after_lifespan.append(original_lifespan_exited == [True])

    def close_redis_client(client: redis.Redis) -> None:
        """Record closure of the client nested inside SlowAPI's Redis storage."""
        closed_redis_clients.append(client)
        redis_closed_after_lifespan.append(original_lifespan_exited == [True])

    @asynccontextmanager
    async def custom_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Represent an application-owned lifespan used by managed workers."""
        yield
        original_lifespan_exited.append(True)

    monkeypatch.setattr(JwtAuthenticator, "close", close)
    monkeypatch.setattr(redis.Redis, "close", close_redis_client)
    manifest = AgentManifestInput.model_validate(
        {
            "name": "mail-agent",
            "description": "Mail service.",
            "skills": ["search"],
            "http": {
                "endpoints": ["chat_completions"],
                "security": {
                    "mode": "jwt",
                    "jwt": {"secret": "${JWT_SIGNING_SECRET}", "allowed_algorithms": ["HS256"]},
                },
                "rate_limit": {
                    "limits": ["60/minute"],
                    "storage_uri": "redis://127.0.0.1:6379/0",
                },
            },
        }
    )
    assert manifest.http is not None
    app = FastAPI(lifespan=custom_lifespan)
    settings = AgentHttpSettingsBuilder({"JWT_SIGNING_SECRET": "test-only-signing-key"}).build(
        manifest.http
    )
    HostingFactory(app).add_agent(_invoke, make_descriptor("mail-agent")).add_http_settings(
        settings
    ).register()

    async def run_lifespan() -> None:
        """Enter and exit the actual FastAPI router lifespan context."""
        async with app.router.lifespan_context(app):
            pass

    asyncio.run(run_lifespan())

    assert original_lifespan_exited == [True]
    assert len(closed) == 1
    assert len(closed_redis_clients) == 1
    assert closed_after_lifespan == [True]
    assert redis_closed_after_lifespan == [True]

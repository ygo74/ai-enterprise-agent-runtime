from __future__ import annotations

import inspect
import json
import os
from collections.abc import Mapping
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from env_loader import ensure_env_loaded

ensure_env_loaded()

try:
    from mcp import ClientSession

    try:
        # Newer MCP SDK name.
        from mcp.client.streamable_http import streamable_http_client
    except Exception:
        # Backward-compatible MCP SDK name.
        from mcp.client.streamable_http import streamablehttp_client as streamable_http_client
except Exception:  # pragma: no cover - import availability depends on local env
    ClientSession = None
    streamable_http_client = None


class MSLearnSearchInput(BaseModel):
    query: str = Field(..., description="Question or topic to search in Microsoft Learn docs")
    locale: str = Field(default="en-us", description="Locale for content, for example en-us or fr-fr")


class MSLearnMCPClient:
    """Minimal streamable-http MCP client wrapper for Microsoft Learn MCP."""

    def __init__(self) -> None:
        self.server_url = os.getenv("MSLEARN_MCP_URL", "https://learn.microsoft.com/api/mcp")
        self.tool_name = os.getenv("MSLEARN_MCP_TOOL", "microsoft_docs_search")

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}

        api_key = os.getenv("MSLEARN_MCP_API_KEY")
        api_key_header = os.getenv("MSLEARN_MCP_API_KEY_HEADER", "Ocp-Apim-Subscription-Key")
        if api_key:
            headers[api_key_header] = api_key

        bearer = os.getenv("MSLEARN_MCP_BEARER_TOKEN")
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"

        return headers

    def _stream_context(self, headers: dict[str, str]) -> Any:
        """Build the streamable-http client context, adapting to the installed MCP SDK signature."""

        try:
            supported_params = inspect.signature(streamable_http_client).parameters
        except (TypeError, ValueError):
            supported_params = {}

        if "headers" in supported_params:
            # Legacy MCP SDK: streamable_http_client(url, headers=...)
            if headers:
                return streamable_http_client(self.server_url, headers=headers)
            return streamable_http_client(self.server_url)

        if "http_client" in supported_params:
            # Newer MCP SDK: streamable_http_client(url, http_client=httpx2.AsyncClient(headers=...))
            http_client = None
            if headers:
                import httpx2

                http_client = httpx2.AsyncClient(headers=headers)
            return streamable_http_client(self.server_url, http_client=http_client)

        return streamable_http_client(self.server_url)

    async def search(self, query: str, locale: str = "en-us") -> str:
        """Calls the remote MCP tool and returns a compact text summary for the LLM."""

        if not query.strip():
            raise ValueError("query must not be empty")

        # Fallback hint when MCP SDK isn't installed in local environment.
        if ClientSession is None or streamable_http_client is None:
            return (
                "MCP SDK unavailable at runtime. Install requirements and retry. "
                f"Planned call: url={self.server_url}, tool={self.tool_name}, query={query!r}, locale={locale!r}"
            )

        # The Microsoft Learn MCP tool only accepts a 'query' parameter (no locale support).
        payload = {"query": query}

        async with self._stream_context(self._headers()) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(self.tool_name, payload)

        # Keep this robust across MCP server payload formats.
        content = getattr(result, "content", None)
        if content is not None:
            parts: list[str] = []
            for block in content:
                text = getattr(block, "text", None)
                if text is not None:
                    parts.append(text)
                else:
                    parts.append(str(block))
            return "\n".join(parts)

        if isinstance(result, Mapping):
            return json.dumps(result, ensure_ascii=True)

        return str(result)


@tool("mslearn_mcp_search", args_schema=MSLearnSearchInput)
async def mslearn_mcp_search(query: str, locale: str = "en-us") -> str:
    """Searches Microsoft Learn through its MCP server for architecture guidance and references."""

    client = MSLearnMCPClient()
    return await client.search(query=query, locale=locale)

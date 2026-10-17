"""A Model Context Protocol server, served over authenticated HTTP.

Two tools over a small in-memory catalogue, and the point of the example is
everything around them: which callers are let in, how that is decided, and what
happens when nobody decided.

Run it in each of the three modes and watch the behaviour change - the tools do not.

    # Refuses to start: nothing said who may call it.
    python server.py

    # A shared secret.
    $env:DEMO_MCP_AUTH_MODE = "api_key"
    $env:DEMO_MCP_HTTP_TOKEN = "choose-a-secret"
    python server.py

    # An identity provider, discoverable by any MCP client.
    $env:DEMO_MCP_AUTH_MODE = "jwt"
    $env:DEMO_MCP_OIDC_ISSUER = "https://keycloak.example/realms/agents"
    $env:DEMO_MCP_RESOURCE_URL = "http://127.0.0.1:9300"
    python server.py

    # Anonymous, because somebody said so.
    $env:DEMO_MCP_AUTH_MODE = "none"
    python server.py
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP
from ygo74.agent_runtime.domains.mcpserver.host import McpServerHost
from ygo74.agent_runtime.domains.mcpserver.http_binding import McpHttpBinding
from ygo74.agent_runtime.domains.mcpserver.settings import McpServerAuthentication

PREFIX = "DEMO_MCP_"
SERVER_NAME = "demo-mcp-server"

# Who a shared secret authenticates: a deployment, not a person.
CALLER = "demo-client"

HOST = "127.0.0.1"
PORT = 9300

BOOKS = {
    "the-mythical-man-month": "Adding manpower to a late software project makes it later.",
    "a-philosophy-of-software-design": "Complexity is anything that makes software hard to understand.",
}


def build_server() -> FastMCP:
    """Assemble the tool surface.

    The bind address goes in the constructor, deliberately. `FastMCP` derives its
    DNS-rebinding allow-list from it here and never revisits it, so setting
    `settings.host` afterwards leaves a server that answers 421 to every caller
    reaching it by any name but this one.
    """
    server = FastMCP(SERVER_NAME, host=HOST, port=PORT)

    @server.tool(description="List the books in the catalogue.")
    def list_books() -> list[str]:
        return sorted(BOOKS)

    @server.tool(description="Return the one-line summary of a book, by its identifier.")
    def summarise_book(book_id: str) -> str:
        summary = BOOKS.get(book_id)
        if summary is None:
            raise ValueError(f"no such book: {book_id!r}")
        return summary

    return server


def main() -> None:
    """Read the configuration, then serve - or refuse, loudly."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Read first. A server that cannot say who may call it must fail here, not once
    # it is already listening.
    authentication = McpServerAuthentication.from_env(PREFIX, caller_id=CALLER)

    McpServerHost(
        policy=authentication.policy,
        binding=McpHttpBinding(host=HOST, port=PORT),
        resource_url=authentication.resource_url,
    ).serve(build_server())


if __name__ == "__main__":
    main()

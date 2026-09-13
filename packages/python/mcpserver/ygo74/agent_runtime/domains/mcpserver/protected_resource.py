"""OAuth 2.1 protected-resource metadata, so a client can find the issuer itself.

The MCP specification expects an HTTP server to behave as an OAuth 2.1 resource
server: answer a credential-less request with a ``WWW-Authenticate`` header naming
where its metadata lives, and publish that metadata at a well-known path (RFC 9728).

That is the whole difference between a server a generic MCP client - VS Code,
Claude Desktop - can connect to by URL alone, and one that needs a human to be told
out of band which realm to authenticate against.

The metadata is published **unauthenticated**, necessarily: a client cannot present
a token before learning where to obtain one. It discloses only what a client needs
to start the flow, and nothing about the tools behind it.

Only published in JWT mode. A server authenticating an API key does not implement
an OAuth flow, and advertising one would be a lie a client would then act on.
"""

from __future__ import annotations

from dataclasses import dataclass

PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"


@dataclass(frozen=True, slots=True)
class ProtectedResource:
    """What this server is, and which authorization server issues for it.

    Args:
        resource_url: The canonical URL of this MCP server, which is also its RFC
            8707 resource indicator - the audience a token must carry.
        issuer: The authorization server tokens come from.
        scopes: Scopes a client should ask for, when the deployment requires any.
    """

    resource_url: str
    issuer: str
    scopes: tuple[str, ...] = ()

    def metadata(self) -> dict[str, object]:
        """The RFC 9728 document."""
        document: dict[str, object] = {
            "resource": self.resource_url,
            "authorization_servers": [self.issuer],
            "bearer_methods_supported": ["header"],
        }
        if self.scopes:
            document["scopes_supported"] = list(self.scopes)
        return document

    def challenge(self) -> str:
        """The ``WWW-Authenticate`` value that points a client at the metadata."""
        return f'Bearer resource_metadata="{self.resource_url}{PROTECTED_RESOURCE_PATH}"'

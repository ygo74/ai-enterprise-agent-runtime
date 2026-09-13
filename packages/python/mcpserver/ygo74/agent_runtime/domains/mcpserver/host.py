"""Hosting a Model Context Protocol server over HTTP.

Over stdio an MCP server's security argument is the operating system: it is a child
process, its credential never leaves it, and the caller talks to it through a pipe
nobody else can open. Over HTTP that argument is gone. The pipe becomes a port and
every process that can reach the port can reach the tools, while nothing else about
the server changes - same tools, same payloads - which is exactly why the difference
is easy to miss.

This host is the part that does not change between servers: the authentication
chain, an open health probe, OAuth discovery, and a start-up check on the one trap
that costs a production incident to find.

**Why a middleware rather than the SDK's `TokenVerifier`.** The MCP SDK can verify a
bearer token, and only that. An API key in ``x-api-key``, a Basic credential, a
Kerberos ticket - none is expressible through it. Running the runtime's
:class:`RequestAuthenticator` as ASGI middleware is what lets one authentication
model serve an agent and an MCP server instead of two models drifting apart.

The authenticated caller is attached to the request scope but is **not** yet the
authority on what a tool operates upon: tools still take the subject they act for as
an argument. Making the authenticated identity authoritative is the next piece of
work, and this host is shaped so that it does not have to be undone first.
"""

from __future__ import annotations

import hmac
import logging
from typing import TYPE_CHECKING, Any

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.authentication_policy import (
    AuthenticationMode,
    AuthenticationPolicy,
)
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtAuthenticator
from ygo74.agent_runtime.domains.mcpserver.http_binding import HEALTH_PATH, McpHttpBinding
from ygo74.agent_runtime.domains.mcpserver.protected_resource import (
    PROTECTED_RESOURCE_PATH,
    ProtectedResource,
)
from ygo74.agent_runtime.domains.mcpserver.server_errors import (
    McpServerConfigurationError,
    McpServerUnreachableError,
)

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from starlette.applications import Starlette

MISDIRECTED_REQUEST = 421

# The scope key the authenticated caller is published under. Named rather than
# inlined because the next piece of work - making that identity authoritative over
# what a tool operates upon - reads it.
AUTH_CONTEXT_KEY = "ygo74.auth_context"

_logger = logging.getLogger(__name__)


class McpServerHost:
    """Serves an MCP application to callers that prove who they are.

    Args:
        policy: Which authentication schemes this server accepts. There is no
            default: serving everyone is a decision, and
            :meth:`AuthenticationPolicy.anonymous` is how it is said.
        binding: Where the server listens and what callers reach it at.
        resource_url: The canonical URL of this server, required in JWT mode so it
            can name itself as an OAuth resource. Ignored otherwise.
        scopes: Scopes a client should request, when the deployment requires any.
    """

    def __init__(
        self,
        *,
        policy: AuthenticationPolicy,
        binding: McpHttpBinding | None = None,
        resource_url: str = "",
        scopes: tuple[str, ...] = (),
    ) -> None:
        self._policy = policy
        self._binding = binding or McpHttpBinding()
        self._authenticator = policy.build()
        self._resource = self._protected_resource(policy, resource_url, scopes)

    @property
    def binding(self) -> McpHttpBinding:
        """Where this server listens."""
        return self._binding

    @property
    def protected_resource(self) -> ProtectedResource | None:
        """The OAuth metadata this server publishes, when it publishes any."""
        return self._resource

    def application(self, tools: Starlette) -> Starlette:
        """Wrap an MCP application with authentication, health and discovery.

        ``tools`` is what ``FastMCP.streamable_http_app()`` returns. The host adds
        routes rather than replacing them, so a server keeps whatever else it
        exposes.
        """
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def health(_request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        async def metadata(_request: Request) -> JSONResponse:
            # Only reachable when a resource was configured, because the route is
            # only added then. A 404 elsewhere is the honest answer: this server
            # implements no OAuth flow.
            assert self._resource is not None  # noqa: S101 - guarded by the route
            return JSONResponse(self._resource.metadata())

        async def guard(request: Request, call_next: Any) -> Any:
            if self._is_open(request.url.path):
                return await call_next(request)

            try:
                context = self._authenticator.authenticate(dict(request.headers))
            except AuthenticationError:
                return self._refusal(request.url.path)
            except Exception as failure:  # noqa: BLE001 - translated, not swallowed
                # An authenticator a host wrote itself. The built-in schemes turn a
                # malformed credential into an AuthenticationError, but Basic,
                # Kerberos or whatever a deployment actually has is arbitrary code
                # on the request path, and an unauthenticated caller able to raise
                # inside the process holding the credential is a log-flood vector on
                # the one surface meant to be hard.
                #
                # Failing closed is the whole translation: a scheme that could not
                # decide is a scheme that did not authenticate.
                _logger.warning(
                    "authenticator %s raised %s; refusing the request",
                    type(self._authenticator).__name__,
                    type(failure).__name__,
                )
                return self._refusal(request.url.path)

            request.scope[AUTH_CONTEXT_KEY] = context
            return await call_next(request)

        tools.router.routes.append(Route(HEALTH_PATH, health, methods=["GET"]))
        if self._resource is not None:
            tools.router.routes.append(Route(PROTECTED_RESOURCE_PATH, metadata, methods=["GET"]))
        tools.add_middleware(BaseHTTPMiddleware, dispatch=guard)
        return tools

    def verify_reachable(self, tools: Starlette) -> None:
        """Refuse to serve an application that would reject its own callers.

        Sends one synthetic request carrying the public host, before the port is
        opened. A ``FastMCP`` server whose DNS-rebinding allow-list was frozen to
        loopback answers 421 here - which is the same answer every real caller would
        get, except that this one happens at start-up where somebody is watching.
        """
        from starlette.testclient import TestClient

        with TestClient(tools) as client:
            response = client.get(
                "/mcp",
                headers={"Host": self._binding.public_host},
                follow_redirects=False,
            )

        if response.status_code != MISDIRECTED_REQUEST:
            return

        raise McpServerUnreachableError(
            f"this server answers 421 to a request for host {self._binding.public_host!r}: "
            "its transport security was derived from a bind address that does not include it. "
            "FastMCP freezes that allow-list at construction, so pass the real bind address to "
            "the constructor rather than assigning to settings afterwards"
        )

    def serve(self, tools: Starlette) -> None:
        """Verify, then serve until stopped."""
        import uvicorn

        self.verify_reachable(tools)
        _logger.info(
            "serving MCP over HTTP on %s:%s as %s - %s",
            self._binding.host,
            self._binding.port,
            self._binding.public_host,
            self._policy.describe(),
        )
        uvicorn.run(self.application(tools), host=self._binding.host, port=self._binding.port)

    def _is_open(self, path: str) -> bool:
        """Whether a path is reachable without a credential.

        Compared exactly rather than by prefix. A probe an orchestrator can call and
        a metadata document a client needs before it has a token are the only two,
        and `/healthzextra` is not either of them.
        """
        return any(hmac.compare_digest(path, open_path) for open_path in self._open_paths())

    def _open_paths(self) -> tuple[str, ...]:
        """Paths reachable without a credential.

        The metadata path is open whether or not this server publishes it. When it
        does, a client must be able to read it before it has a token; when it does
        not, routing answers 404 - which is the honest "I am not an OAuth resource
        server". Guarding it instead would answer 401, and a client probing for
        OAuth support would read that as "there is a flow here, you just need a
        credential".
        """
        return (HEALTH_PATH, PROTECTED_RESOURCE_PATH)

    def _refusal(self, path: str) -> Any:
        """Answer a caller that could not prove itself.

        No detail about what was wrong: which part failed is information a guesser
        can use, and the operator has the server log.
        """
        from starlette.responses import JSONResponse

        _logger.warning("refused an unauthenticated request to %s", path)
        headers = {} if self._resource is None else {"WWW-Authenticate": self._resource.challenge()}
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=headers)

    @staticmethod
    def _protected_resource(
        policy: AuthenticationPolicy,
        resource_url: str,
        scopes: tuple[str, ...],
    ) -> ProtectedResource | None:
        """Build the OAuth metadata, when this server is an OAuth resource server."""
        if policy.mode is not AuthenticationMode.JWT:
            return None

        if not resource_url.strip():
            raise McpServerConfigurationError(
                "serving JWT-authenticated MCP requires resource_url: a resource server that "
                "cannot name itself cannot be discovered, and a client has no way to learn "
                "which issuer to authenticate against"
            )

        issuer = _issuer_of(policy)
        if not issuer:
            raise McpServerConfigurationError(
                "serving JWT-authenticated MCP requires an issuer in the validation config: "
                "without one there is no authorization server to advertise"
            )

        return ProtectedResource(resource_url.rstrip("/"), issuer, scopes)


def _issuer_of(policy: AuthenticationPolicy) -> str:
    """Read the issuer out of the policy's JWT authenticator."""
    for authenticator in policy.authenticators:
        config = getattr(authenticator, "config", None) if isinstance(authenticator, JwtAuthenticator) else None
        if config is not None and config.issuer:
            return str(config.issuer)
    return ""

"""OAuth pieces that are not any one provider's business.

Three things here are the same whichever authorisation server an application
talks to, and one of them is a security control that must not be lost in a
refactor.

**Consent on the loopback interface.** The authorisation server sends the person
back to a URL the application controls. Listening on ``127.0.0.1`` keeps the
authorisation code on the machine: it never crosses a network and never passes
through a third party. The listener serves exactly one redirect and stops, so
nothing is left accepting connections once consent is over.

**Token storage on disk.** So a restart does not cost a new consent. The client
identity is deliberately *not* stored: it is configuration, supplied on every
start, which also means a rotated secret takes effect immediately.

**Scope pinning.** The MCP SDK replaces the configured scope with whatever the
resource server advertises, and re-widens it when a call comes back with
``insufficient_scope``. For at least one well-known server that advertised set
includes full mailbox control, permanent deletion included, which is far beyond
what an application asked for. :class:`PinnedScopeOAuthProvider` re-pins the
requested scope before every authorisation attempt, neutralising both the initial
widening and the later step-up. If the server genuinely refuses to work within
those scopes the call fails and says so, which is a better outcome than silently
holding a key to everything.

What stays with the application: which scopes it needs, which client it is, and
where the token file lives.
"""

from __future__ import annotations

import json
import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ygo74.agent_runtime.domains.mcp.mcp_errors import McpToolUnavailableError

try:  # pragma: no cover - depends on the optional `mcp` extra
    from mcp.client.auth import OAuthClientProvider, TokenStorage
    from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

    _MCP_AVAILABLE = True
except Exception:  # noqa: BLE001  # pragma: no cover - the extra is optional by design
    OAuthClientProvider = object  # type: ignore[assignment,misc]
    TokenStorage = object  # type: ignore[assignment,misc]
    OAuthClientInformationFull = Any  # type: ignore[assignment,misc]
    OAuthToken = Any  # type: ignore[assignment,misc]
    _MCP_AVAILABLE = False

CALLBACK_PATH = "/oauth/callback"
LOOPBACK_HOST = "127.0.0.1"

_DONE = (
    "<html><body><h3>Authorisation received.</h3>"
    "<p>You can close this tab and return to the terminal.</p></body></html>"
)

_logger = logging.getLogger(__name__)


def loopback_redirect_uri(port: int) -> str:
    """Where the authorisation server sends the person back."""
    return f"http://localhost:{port}{CALLBACK_PATH}"


class LoopbackConsent:
    """Serves exactly one redirect on the loopback interface, then stops."""

    def __init__(self, port: int, *, timeout_seconds: int = 300) -> None:
        self._port = port
        self._timeout = timeout_seconds

    async def obtain(self, authorisation_url: str) -> tuple[str, str | None]:
        """Open the browser, wait for one redirect, return its code and state.

        Raises:
            McpToolUnavailableError: the redirect carried no authorisation code,
                which is what a refusal at the consent screen looks like.
        """
        captured: dict[str, str] = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                query = parse_qs(urlparse(self.path).query)
                captured.update({key: values[0] for key, values in query.items() if values})
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(_DONE.encode("utf-8"))

            def log_message(self, *_: Any) -> None:
                """Silence the default stderr logging: it prints the query string."""

        webbrowser.open(authorisation_url)
        with HTTPServer((LOOPBACK_HOST, self._port), Handler) as server:
            server.timeout = self._timeout
            server.handle_request()

        code = captured.get("code")
        if not code:
            raise McpToolUnavailableError("authorisation was not granted")
        return code, captured.get("state")


class FileTokenStorage(TokenStorage):  # type: ignore[misc]
    """Keeps issued tokens on disk, between runs.

    Args:
        token_file: Where to keep them. Written with owner-only permissions.
        client_info: The pre-registered client, returned as is so no dynamic
            registration happens - several providers do not support it, and one
            that did would register a client nobody decided on.
    """

    def __init__(self, token_file: Path, client_info: OAuthClientInformationFull) -> None:
        self._token_file = token_file
        self._client_info = client_info

    async def get_tokens(self) -> OAuthToken | None:
        """Return the tokens of a previous authorisation, if any."""
        if not self._token_file.is_file():
            return None
        try:
            return OAuthToken.model_validate_json(self._token_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A damaged token file must cost a new consent, never a crash.
            _logger.info("stored tokens could not be read; a new authorisation will be requested")
            return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Persist the issued tokens for the next run."""
        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        self._token_file.write_text(tokens.model_dump_json(), encoding="utf-8")
        self._token_file.chmod(0o600)

    async def get_client_info(self) -> OAuthClientInformationFull:
        """Return the pre-registered client."""
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Ignore a client the server would like us to register.

        The client is configuration. Accepting one from the server would mean an
        identity nobody chose, and a rotated secret that never took effect.
        """
        del client_info


class PinnedScopeOAuthProvider(OAuthClientProvider):  # type: ignore[misc]
    """Requests only the scopes the application actually needs.

    Re-pinning before every authorisation attempt neutralises both the SDK's
    initial widening to whatever the resource server advertises, and its later
    step-up when a call returns ``insufficient_scope``.

    Dropping this class, or reimplementing it casually, silently grants the
    application everything the server is willing to offer.
    """

    def __init__(self, *args: Any, pinned_scope: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pinned_scope = pinned_scope

    @property
    def pinned_scope(self) -> str:
        """The scope this provider will ask for, whatever it is told."""
        return self._pinned_scope

    async def _perform_authorization_code_grant(self) -> tuple[str, str]:
        """Ask for the pinned scopes, whatever the server advertised."""
        self.context.client_metadata.scope = self._pinned_scope
        return await super()._perform_authorization_code_grant()  # type: ignore[misc,no-any-return]


def describe_scopes(scopes: str) -> str:
    """Render a scope string for a log line, without inviting a copy-paste secret."""
    return json.dumps(sorted(scopes.split()))

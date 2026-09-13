"""Tests of MCP server hosting: transport, authentication and discovery.

An MCP server reached over stdio is defended by the operating system: it is a child
process, its credential never leaves it, and the caller talks to it through a pipe
nobody else can open. Over HTTP that argument is gone, the pipe becomes a port, and
every process that can reach the port can reach the tools. Nothing else about the
server changes, which is exactly why the difference is easy to miss.

Three groups of test below, in descending order of how much they matter.

The first is the security posture: anonymous only when somebody said so, every other
mode refusing a caller that cannot prove itself, and the health probe open in all of
them because an orchestrator must be able to ask whether a process is alive without
being handed a credential to do it.

The second is the trap. `FastMCP` derives its DNS-rebinding allow-list from the bind
address at construction and never revisits it, so a server built with the default
address answers every request carrying a service name in `Host` with 421 - after
authentication, before any tool, with the health probe still green. That failure was
found in production-shaped testing, not in a unit test, and this is where it stops
being possible.

The third is OAuth 2.1 discovery, which is what lets a generic MCP client find the
issuer by itself instead of being told out of band.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ygo74.agent_runtime.domains.auth.apikey_authenticator import StaticApiKeyUserResolver
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtValidationConfig
from ygo74.agent_runtime.domains.mcpserver.host import McpServerHost
from ygo74.agent_runtime.domains.mcpserver.http_binding import HEALTH_PATH, McpHttpBinding
from ygo74.agent_runtime.domains.mcpserver.protected_resource import PROTECTED_RESOURCE_PATH
from ygo74.agent_runtime.domains.mcpserver.server_errors import (
    McpServerConfigurationError,
    McpServerUnreachableError,
)

SECRET = "a-shared-deployment-secret"  # noqa: S105 - a fixture, not a credential
SERVICE_HOST = "mail-mcp-gmail:9100"


@dataclass(frozen=True)
class _TransportSecurity:
    """The shape of `mcp.server.transport_security.TransportSecuritySettings`.

    Reproduced rather than imported so the check can be exercised without standing
    up a FastMCP server. The real thing is exercised too - see
    `test_a_real_fastmcp_server_is_read_correctly`.
    """

    enable_dns_rebinding_protection: bool
    allowed_hosts: list[str]


_LOOPBACK_ONLY = _TransportSecurity(True, ["127.0.0.1:*", "localhost:*", "[::1]:*"])


def _policy() -> AuthenticationPolicy:
    return AuthenticationPolicy.api_key(
        StaticApiKeyUserResolver({SECRET: ResolvedUser(user_id="svc-mail-agent")}),
        header_name="authorization",
        scheme="Bearer",
    )


def _tools_app() -> Starlette:
    """Stands in for what `FastMCP.streamable_http_app()` returns.

    The tool surface is irrelevant here: every test is about what happens before a
    tool is reached, and echoing the caller proves the request got through.
    """

    async def tools(request):  # noqa: ANN001, ANN202 - a Starlette route
        return JSONResponse({"reached": True, "host": request.headers.get("host", "")})

    return Starlette(routes=[Route("/mcp", tools, methods=["GET", "POST"])])


def _client(
    policy: AuthenticationPolicy | None = None,
    *,
    binding: McpHttpBinding | None = None,
    resource_url: str = "",
) -> TestClient:
    host = McpServerHost(
        policy=policy or _policy(),
        binding=binding or McpHttpBinding(host="0.0.0.0", port=9100),  # noqa: S104 - what a container binds
        resource_url=resource_url,
    )
    return TestClient(host.application(_tools_app()))


class TestTheSecurityPosture:
    """What each mode guarantees, and what none of them guarantees."""

    def test_a_call_without_a_credential_is_refused(self):
        with _client() as client:
            assert client.get("/mcp").status_code == 401

    def test_a_call_with_the_wrong_credential_is_refused(self):
        with _client() as client:
            response = client.get("/mcp", headers={"Authorization": "Bearer not-the-secret"})

        assert response.status_code == 401

    def test_a_credentialled_call_reaches_the_tools(self):
        with _client() as client:
            response = client.get("/mcp", headers={"Authorization": f"Bearer {SECRET}"})

        assert response.status_code == 200
        assert response.json()["reached"] is True

    def test_the_refusal_says_nothing_about_what_was_wrong(self):
        """Which part failed is information a guesser can use."""
        with _client() as client:
            body = client.get("/mcp", headers={"Authorization": "Bearer nope"}).json()

        assert SECRET not in json.dumps(body)
        assert "invalid" not in json.dumps(body).lower()

    @pytest.mark.parametrize(
        "header",
        [
            "Bearer caf\xe9".encode("latin-1"),
            b"\xff\xfe",
            "Bearer \U0001f512".encode(),
        ],
    )
    def test_a_credential_we_cannot_even_represent_is_refused_not_raised(self, header):
        """A refusal, never a traceback.

        Sent as raw bytes, which is what a hostile caller does - an HTTP client
        refuses to encode these as text, and that refusal is not a control we get to
        rely on. Starlette decodes header bytes as latin-1, so any byte at all
        reaches the guard, and an unauthenticated caller able to raise inside the
        process holding the credential is a log-flood vector on the one surface
        meant to be hard.
        """
        with _client() as client:
            assert client.get("/mcp", headers={"Authorization": header}).status_code == 401

    def test_an_anonymous_server_serves_everyone(self):
        with _client(AuthenticationPolicy.anonymous()) as client:
            assert client.get("/mcp").status_code == 200

    def test_an_anonymous_server_still_answers_the_probe(self):
        with _client(AuthenticationPolicy.anonymous()) as client:
            assert client.get(HEALTH_PATH).status_code == 200


class TestAnAuthenticatorThatMisbehaves:
    """The extension point is arbitrary code on the request path.

    The built-in schemes turn a malformed credential into an `AuthenticationError`.
    A Basic or Kerberos authenticator a deployment wrote itself might raise anything
    at all, and an unauthenticated caller able to produce a traceback inside the
    process holding the credential is a log-flood vector on exactly the surface this
    host exists to harden.
    """

    class Exploding:
        """A host-supplied scheme that fails the way real code fails."""

        def __init__(self, failure: Exception) -> None:
            self._failure = failure

        @property
        def auth_type(self) -> str:
            return "exploding"

        @property
        def header_name(self) -> str:
            return "authorization"

        def can_authenticate(self, headers) -> bool:
            return "authorization" in headers

        def missing_credential_error(self):
            from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError

            return AuthenticationError(code="missing", message="Missing credential")

        def authenticate(self, headers):
            raise self._failure

    @pytest.mark.parametrize(
        "failure",
        [
            TypeError("comparing strings with non-ASCII characters is not supported"),
            ValueError("malformed credential"),
            KeyError("a claim nobody checked for"),
            RuntimeError("the directory server is down"),
        ],
    )
    def test_the_caller_is_refused_rather_than_handed_a_traceback(self, failure):
        with _client(AuthenticationPolicy.of(self.Exploding(failure))) as client:
            response = client.get("/mcp", headers={"Authorization": "anything"})

        assert response.status_code == 401

    def test_the_refusal_leaks_nothing_about_the_failure(self):
        """An operator has the log; a caller gets no map of the internals."""
        secret_in_message = RuntimeError("connection to ldap://internal-dc-01 failed")

        with _client(AuthenticationPolicy.of(self.Exploding(secret_in_message))) as client:
            body = client.get("/mcp", headers={"Authorization": "anything"}).text

        assert "internal-dc-01" not in body
        assert "ldap" not in body.lower()


class TestTheHealthProbe:
    """Open in every mode, and saying nothing but that the process is alive."""

    def test_it_answers_without_a_credential(self):
        with _client() as client:
            response = client.get(HEALTH_PATH)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_it_discloses_nothing_else(self):
        with _client() as client:
            body = client.get(HEALTH_PATH).json()

        assert set(body) == {"status"}

    def test_a_path_that_merely_starts_like_it_is_still_guarded(self):
        """An exact match, not a prefix: `/healthz/../mcp` must not be a way in."""
        with _client() as client:
            assert client.get(f"{HEALTH_PATH}extra").status_code == 401

    @pytest.mark.parametrize("path", ["/%C3%A9", "/caf%C3%A9", "/mcp/%E2%98%83"])
    def test_a_non_ascii_path_is_refused_rather_than_crashing(self, path):
        """The same trap as a non-ASCII credential, arriving through the path.

        ASGI servers percent-decode into `scope["path"]`, so any caller can put any
        byte there. Comparing it with `hmac.compare_digest` raised `TypeError` on
        non-ASCII text - outside the guard's own failure handling, so it surfaced as
        a 500 and a traceback in the log of a credential-holding process, once per
        unauthenticated request. Constant time buys nothing here anyway: the open
        paths are published constants, not secrets.
        """
        with TestClient(
            McpServerHost(policy=_policy(), binding=McpHttpBinding(host="0.0.0.0", port=9100)).application(  # noqa: S104
                _catch_all_app()
            ),
            raise_server_exceptions=False,
        ) as client:
            assert client.get(path).status_code == 401


class TestTheMisdirectedRequestTrap:
    """The defect this host exists to make impossible.

    `FastMCP` freezes its DNS-rebinding allow-list to loopback when built with the
    default bind address, and enforces it *inside* the streamable HTTP handler. A
    server deployed in a container then answers every real request - which arrives
    with a service name in `Host` - with 421, while the health probe stays green
    because the probe never reaches that handler. Nothing says why.

    The allow-list is read rather than probed, because the only route that enforces
    it is the one this host has just put an authentication guard in front of: a
    synthetic request would be refused at the door and learn nothing.
    """

    def _host(self) -> McpServerHost:
        return McpServerHost(
            policy=_policy(),
            binding=McpHttpBinding(host="0.0.0.0", port=9100, public_host=SERVICE_HOST),  # noqa: S104
        )

    def test_a_service_name_in_host_reaches_the_tools(self):
        with _client() as client:
            response = client.get(
                "/mcp",
                headers={"Authorization": f"Bearer {SECRET}", "Host": SERVICE_HOST},
            )

        assert response.status_code != 421
        assert response.status_code == 200

    def test_a_loopback_allow_list_refuses_to_serve_a_service_name(self):
        """Loud at start-up rather than silent at the first tool call."""
        with pytest.raises(McpServerUnreachableError, match="421"):
            self._host().verify_reachable(_LOOPBACK_ONLY)

    def test_an_allow_list_covering_the_public_host_is_accepted(self):
        self._host().verify_reachable(_TransportSecurity(True, [f"{SERVICE_HOST}", "127.0.0.1:*"]))

    def test_a_wildcard_pattern_is_honoured(self):
        """FastMCP writes its allow-list with port wildcards."""
        self._host().verify_reachable(_TransportSecurity(True, ["mail-mcp-gmail:*"]))

    def test_protection_switched_off_accepts_everything(self):
        """What FastMCP produces for any non-loopback bind address."""
        self._host().verify_reachable(_TransportSecurity(False, ["127.0.0.1:*"]))

    def test_no_transport_security_at_all_accepts_everything(self):
        self._host().verify_reachable(None)

    def test_the_refusal_explains_the_cause_rather_than_the_symptom(self):
        with pytest.raises(McpServerUnreachableError) as refusal:
            self._host().verify_reachable(_LOOPBACK_ONLY)

        message = str(refusal.value)
        assert SERVICE_HOST in message
        assert "127.0.0.1:*" in message
        assert "bind address" in message

    def test_a_loopback_deployment_is_not_tripped_up_by_its_own_defaults(self):
        """The common workstation case must stay silent."""
        host = McpServerHost(policy=_policy(), binding=McpHttpBinding(host="127.0.0.1", port=9100))

        host.verify_reachable(_LOOPBACK_ONLY)

    def test_a_real_fastmcp_server_is_read_correctly(self):
        """The reproduction above is only worth as much as this.

        Both halves of the trap, taken from the library rather than described: a
        loopback bind freezes the allow-list, a container bind switches the
        protection off entirely.
        """
        from mcp.server.fastmcp import FastMCP

        trapped = FastMCP("probe", host="127.0.0.1", port=9100)
        correct = FastMCP("probe", host="0.0.0.0", port=9100)  # noqa: S104 - what a container binds

        with pytest.raises(McpServerUnreachableError):
            self._host().verify_reachable(trapped.settings.transport_security)

        self._host().verify_reachable(correct.settings.transport_security)

    @pytest.mark.parametrize(
        ("allowed", "public_host", "reachable"),
        [
            # The dangerous direction. `["*"]` is how somebody writes "allow every
            # host", `fnmatch` accepts it, and FastMCP refuses every request - the
            # green-at-boot, 421-for-everyone incident this check exists to prevent.
            (["*"], "mail-mcp-gmail:9100", False),
            (["*.internal"], "mail.internal", False),
            (["mail?mcp:9100"], "mail-mcp:9100", False),
            # The other direction: `fnmatch` reads `[::1]` as a character class and
            # refuses a correctly configured IPv6 deployment.
            (["127.0.0.1:*", "localhost:*", "[::1]:*"], "[::1]:9100", True),
            # What FastMCP really accepts.
            (["mail-mcp-gmail:9100"], "mail-mcp-gmail:9100", True),
            (["mail-mcp-gmail:*"], "mail-mcp-gmail:9100", True),
            (["mail-mcp-gmail:*"], "mail-mcp-gmail-2:9100", False),
        ],
    )
    def test_the_allow_list_is_matched_as_fastmcp_matches_it(self, allowed, public_host, reachable):
        """Its grammar is exact-or-`:*`. Nothing wider, nothing narrower."""
        host = McpServerHost(
            policy=_policy(),
            binding=McpHttpBinding(host="0.0.0.0", port=9100, public_host=public_host),  # noqa: S104
        )
        security = _TransportSecurity(True, allowed)

        if reachable:
            host.verify_reachable(security)
            return

        with pytest.raises(McpServerUnreachableError):
            host.verify_reachable(security)

    def test_the_matching_agrees_with_the_library(self):
        """Checked against FastMCP's own validator, not against a description."""
        from mcp.server.transport_security import TransportSecurityMiddleware, TransportSecuritySettings

        middleware = TransportSecurityMiddleware(TransportSecuritySettings())
        cases = [
            (["*"], "mail-mcp-gmail:9100"),
            (["*.internal"], "mail.internal"),
            (["[::1]:*"], "[::1]:9100"),
            (["mail-mcp-gmail:*"], "mail-mcp-gmail:9100"),
            (["mail-mcp-gmail:9100"], "mail-mcp-gmail:9100"),
        ]

        for allowed, public_host in cases:
            middleware.settings.allowed_hosts = allowed
            host = McpServerHost(
                policy=_policy(),
                binding=McpHttpBinding(host="0.0.0.0", port=9100, public_host=public_host),  # noqa: S104
            )
            mine = _accepts(host, _TransportSecurity(True, allowed))

            assert mine == middleware._validate_host(public_host), f"{allowed} vs {public_host}"


class TestTheDerivedPublicHost:
    """A bind address turned into something a caller can actually put in `Host`."""

    def test_an_ipv6_bind_is_bracketed(self):
        """`::1:9100` is not an authority - the colons are indistinguishable."""
        assert McpHttpBinding(host="::1", port=9100).public_host == "[::1]:9100"

    def test_an_already_bracketed_address_is_left_alone(self):
        assert McpHttpBinding(host="[::1]", port=9100).public_host == "[::1]:9100"

    def test_an_ipv4_bind_is_not_bracketed(self):
        assert McpHttpBinding(host="127.0.0.1", port=9100).public_host == "127.0.0.1:9100"

    def test_an_ipv6_wildcard_still_falls_back_to_loopback(self):
        assert McpHttpBinding(host="::", port=9100).public_host == "localhost:9100"


class TestOAuthProtectedResourceDiscovery:
    """What lets a generic MCP client find the issuer without being told."""

    def _jwt_client(self, resource_url: str = "https://mail-mcp.example") -> TestClient:
        return _client(
            AuthenticationPolicy.jwt(JwtValidationConfig(issuer="https://idp.example/realms/agents")),
            resource_url=resource_url,
        )

    def test_the_metadata_is_published_unauthenticated(self):
        """A client cannot present a token before learning where to get one."""
        with self._jwt_client() as client:
            response = client.get(PROTECTED_RESOURCE_PATH)

        assert response.status_code == 200

    def test_it_names_the_resource_and_its_authorization_server(self):
        with self._jwt_client() as client:
            body = client.get(PROTECTED_RESOURCE_PATH).json()

        assert body["resource"] == "https://mail-mcp.example"
        assert body["authorization_servers"] == ["https://idp.example/realms/agents"]
        assert body["bearer_methods_supported"] == ["header"]

    def test_a_refusal_points_at_the_metadata(self):
        with self._jwt_client() as client:
            response = client.get("/mcp")

        assert response.status_code == 401
        challenge = response.headers["WWW-Authenticate"]
        assert challenge.startswith("Bearer ")
        assert f'resource_metadata="https://mail-mcp.example{PROTECTED_RESOURCE_PATH}"' in challenge

    def test_an_api_key_server_publishes_no_oauth_metadata(self):
        """Advertising an OAuth flow a server does not implement would be a lie."""
        with _client() as client:
            assert client.get(PROTECTED_RESOURCE_PATH).status_code == 404

    def test_an_api_key_refusal_carries_no_oauth_challenge(self):
        with _client() as client:
            response = client.get("/mcp")

        assert "WWW-Authenticate" not in response.headers

    def test_jwt_without_a_resource_url_is_refused_at_construction(self):
        """A resource server that cannot name itself cannot be discovered."""
        with pytest.raises(McpServerConfigurationError, match="resource_url"):
            McpServerHost(
                policy=AuthenticationPolicy.jwt(JwtValidationConfig(issuer="https://idp.example")),
                binding=McpHttpBinding(host="0.0.0.0", port=9100),  # noqa: S104
            )


class TestTheBinding:
    """Where the server listens, and what it calls itself."""

    def test_the_public_host_defaults_to_the_bind_address(self):
        binding = McpHttpBinding(host="127.0.0.1", port=9100)

        assert binding.public_host == "127.0.0.1:9100"

    def test_an_explicit_public_host_wins(self):
        binding = McpHttpBinding(host="0.0.0.0", port=9100, public_host=SERVICE_HOST)  # noqa: S104

        assert binding.public_host == SERVICE_HOST

    def test_a_wildcard_bind_has_no_usable_public_host_of_its_own(self):
        """0.0.0.0 is not a name anything can address, so it must not become one."""
        binding = McpHttpBinding(host="0.0.0.0", port=9100)  # noqa: S104

        assert binding.public_host == "localhost:9100"


def _accepts(host: McpServerHost, security: _TransportSecurity) -> bool:
    """Whether the host would serve, as a boolean rather than an exception."""
    try:
        host.verify_reachable(security)
    except McpServerUnreachableError:
        return False
    return True


def _catch_all_app() -> Starlette:
    """Answers every path, so a refusal can only come from the guard."""

    async def anything(_request):  # noqa: ANN001, ANN202 - a Starlette route
        return JSONResponse({"reached": True})

    return Starlette(routes=[Route("/{path:path}", anything, methods=["GET", "POST"])])


def _misdirecting_app() -> Starlette:
    """An application that rejects any Host it was not built for.

    Kept as a shape reference for what `TransportSecurityMiddleware` does, and used
    by nothing that probes it: the check reads the allow-list instead.
    """

    async def guard(request):  # noqa: ANN001, ANN202 - a Starlette route
        host = request.headers.get("host", "")
        if not host.startswith(("127.0.0.1", "localhost", "[::1]", "testserver")):
            return JSONResponse({"error": "Invalid Host header"}, status_code=421)
        return JSONResponse({"reached": True})

    return Starlette(
        routes=[
            Route("/mcp", guard, methods=["GET", "POST"]),
            Route(HEALTH_PATH, guard, methods=["GET"]),
        ]
    )

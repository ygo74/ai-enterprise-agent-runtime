"""Tests of the Model Context Protocol plumbing.

The binding rules matter because they decide what a model is offered. A tool a
server cannot actually perform, advertised anyway, fails on the first call - and
for a gated operation that means failing *after* somebody approved it.

The scope-pinning test matters for a blunter reason: without it, that control
could be dropped in a refactor and the only symptom would be an application
quietly holding far broader access than it asked for.
"""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from enum import StrEnum
from pathlib import Path

import pytest
from ygo74.agent_runtime.domains.mcp.binding import (
    McpConnection,
    McpServerBinding,
    McpServerBindingLoader,
    McpTransport,
)
from ygo74.agent_runtime.domains.mcp.dialects import DialectRegistry
from ygo74.agent_runtime.domains.mcp.mcp_errors import (
    McpBindingError,
    McpToolUnavailableError,
)
from ygo74.agent_runtime.domains.mcp.oauth import (
    CALLBACK_PATH,
    PinnedScopeOAuthProvider,
    loopback_redirect_uri,
)


class Capability(StrEnum):
    """An application's own capability names - the library never interprets them."""

    SEARCH = "search_items"
    SEND = "send_item"


def write(tmp_path: Path, body: str, name: str = "server.yaml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def loader() -> McpServerBindingLoader[Capability]:
    return McpServerBindingLoader(Capability)


HTTP_BINDING = """
server: reference
transport: http
url: https://example.test/mcp
capabilities:
  - search_items
  - send_item
tools:
  search_items: remote_search
  send_item: remote_send
"""


def test_a_binding_declares_how_to_reach_a_server(tmp_path: Path) -> None:
    binding = loader().load(write(tmp_path, HTTP_BINDING))

    assert binding.server == "reference"
    assert binding.transport is McpTransport.HTTP
    assert binding.url == "https://example.test/mcp"
    assert binding.dialect == "native"


def test_a_binding_reports_only_what_it_declared(tmp_path: Path) -> None:
    """What a server does not declare is never offered to the model."""
    body = HTTP_BINDING.replace("  - send_item\n", "")
    binding = loader().load(write(tmp_path, body))

    assert binding.supports(Capability.SEARCH)
    assert not binding.supports(Capability.SEND)


def test_a_binding_translates_a_tool_name(tmp_path: Path) -> None:
    binding = loader().load(write(tmp_path, HTTP_BINDING))

    assert binding.remote("search_items") == "remote_search"


def test_a_binding_refuses_a_tool_it_never_named(tmp_path: Path) -> None:
    binding = loader().load(write(tmp_path, HTTP_BINDING))

    with pytest.raises(McpBindingError, match="declares no tool named"):
        binding.remote("archive_item")


def test_a_binding_fails_now_rather_than_on_the_first_call(tmp_path: Path) -> None:
    """A capability with no tool behind it would fail after a user approved it."""
    body = HTTP_BINDING.replace("  send_item: remote_send\n", "")
    binding = loader().load(write(tmp_path, body))

    with pytest.raises(McpBindingError, match="names no tool for them"):
        binding.require_declared_capabilities()


def test_a_dialect_needing_an_unnamed_tool_fails_now(tmp_path: Path) -> None:
    binding = loader().load(write(tmp_path, HTTP_BINDING))

    with pytest.raises(McpBindingError, match="missing tool names"):
        binding.require_aliases(["search_items", "archive_item"])


def test_an_unknown_capability_is_refused(tmp_path: Path) -> None:
    body = HTTP_BINDING.replace("  - send_item", "  - delete_everything")

    with pytest.raises(McpBindingError, match="unknown capabilities"):
        loader().load(write(tmp_path, body))


def test_a_binding_declaring_no_capability_is_refused(tmp_path: Path) -> None:
    body = "server: s\ntransport: http\nurl: https://x.test\ncapabilities: []\ntools: {}\n"

    with pytest.raises(McpBindingError, match="at least one capability"):
        loader().load(write(tmp_path, body))


def test_binding_errors_can_be_preserved_by_an_application(tmp_path: Path) -> None:
    class ApplicationBindingError(Exception):
        pass

    application_loader = McpServerBindingLoader(Capability, error_factory=ApplicationBindingError)
    body = HTTP_BINDING.replace("transport: http", "transport: unknown")

    with pytest.raises(ApplicationBindingError, match="must be one of"):
        application_loader.load(write(tmp_path, body))

    binding = McpServerBinding(
        server="reference",
        transport=McpTransport.HTTP,
        capabilities=[Capability.SEARCH],
        tools={},
        url="https://example.test/mcp",
        error_factory=ApplicationBindingError,
    )
    with pytest.raises(ApplicationBindingError, match="declares no tool"):
        binding.remote("search_items")


def test_an_unknown_transport_names_the_accepted_ones(tmp_path: Path) -> None:
    body = HTTP_BINDING.replace("transport: http", "transport: carrier-pigeon")

    with pytest.raises(McpBindingError, match="must be one of"):
        loader().load(write(tmp_path, body))


def test_an_http_binding_without_an_endpoint_is_refused(tmp_path: Path) -> None:
    body = HTTP_BINDING.replace("url: https://example.test/mcp\n", "")

    with pytest.raises(McpBindingError, match="requires 'url'"):
        loader().load(write(tmp_path, body))


def test_a_stdio_binding_without_a_command_is_refused(tmp_path: Path) -> None:
    body = HTTP_BINDING.replace("transport: http", "transport: stdio").replace(
        "url: https://example.test/mcp\n", ""
    )

    with pytest.raises(McpBindingError, match="requires 'command'"):
        loader().load(write(tmp_path, body))


def test_a_file_that_is_not_a_mapping_is_refused(tmp_path: Path) -> None:
    with pytest.raises(McpBindingError, match="must contain a mapping"):
        loader().load(write(tmp_path, "- just\n- a list\n"))


def test_a_missing_file_is_reported_rather_than_crashing(tmp_path: Path) -> None:
    with pytest.raises(McpBindingError, match="could not read"):
        loader().load(tmp_path / "absent.yaml")


def test_the_read_only_variable_is_carried_but_not_interpreted(tmp_path: Path) -> None:
    """Its name is schema; what to do about it is a deployment decision."""
    body = HTTP_BINDING + "read_only_variable: WIKI_MCP_READ_ONLY\n"
    binding = loader().load(write(tmp_path, body))

    assert binding.read_only_variable == "WIKI_MCP_READ_ONLY"
    assert binding.supports(Capability.SEND), "the library must not withdraw a capability by itself"


def _binding(dialect: str = "native") -> McpServerBinding[Capability]:
    return McpServerBinding(
        server="reference",
        transport=McpTransport.HTTP,
        capabilities=[Capability.SEARCH],
        tools={"search_items": "remote_search"},
        dialect=dialect,
        url="https://example.test/mcp",
    )


def test_a_registry_builds_the_dialect_a_binding_asks_for() -> None:
    registry: DialectRegistry[str, []] = DialectRegistry({"native": lambda binding: f"native:{binding.server}"})

    assert registry.build(_binding()) == "native:reference"


def test_a_registry_names_the_alternatives_when_a_dialect_is_unknown() -> None:
    registry: DialectRegistry[str, []] = DialectRegistry({"native": lambda binding: "x", "gmail": lambda binding: "y"})

    with pytest.raises(McpToolUnavailableError, match="gmail, native"):
        registry.build(_binding("imap"))


def test_a_registry_refuses_to_replace_a_dialect_silently() -> None:
    """Replacing quietly is how a deployment talks to a server nobody chose."""
    registry: DialectRegistry[str, []] = DialectRegistry({"native": lambda binding: "x"})

    with pytest.raises(McpToolUnavailableError, match="already registered"):
        registry.register("native", lambda binding: "y")


def test_a_registry_passes_what_a_dialect_needs_through() -> None:
    registry: DialectRegistry[str, [str]] = DialectRegistry(
        {"native": lambda binding, owner: f"{binding.server}:{owner}"}
    )

    assert registry.build(_binding(), "ada") == "reference:ada"


def test_a_registry_can_raise_an_application_error() -> None:
    class ApplicationUnavailableError(Exception):
        pass

    registry: DialectRegistry[str, []] = DialectRegistry(
        {"native": lambda binding: "x"},
        unavailable=ApplicationUnavailableError,
    )

    with pytest.raises(ApplicationUnavailableError, match="already registered"):
        registry.register("native", lambda binding: "y")


def test_http_headers_reach_only_the_http_transport(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    from ygo74.agent_runtime.domains.mcp import binding as binding_module

    received: dict[str, object] = {}

    @asynccontextmanager
    async def fake_transport(url: str, **kwargs: object):
        received["url"] = url
        received.update(kwargs)
        yield object(), object(), None

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def initialize(self) -> None:
            return None

    monkeypatch.setattr(binding_module, "streamablehttp_client", fake_transport)
    monkeypatch.setattr(binding_module, "ClientSession", lambda *args, **kwargs: FakeSession())
    headers = {"Authorization": "Bearer secret-value"}
    connection = McpConnection(_binding(), headers=headers)

    async def scenario() -> None:
        await connection.session()
        await connection.aclose()

    import asyncio

    asyncio.run(scenario())

    assert received["headers"] == headers
    assert "secret-value" not in repr(connection)
    assert "secret-value" not in caplog.text


def test_the_redirect_stays_on_the_loopback_interface() -> None:
    """An authorisation code must not cross a network or a third party."""
    uri = loopback_redirect_uri(8765)

    assert uri == f"http://localhost:8765{CALLBACK_PATH}"
    assert "localhost" in uri


def test_the_provider_repins_the_scope_before_every_authorisation() -> None:
    """The control that must survive every refactor of this module.

    Without it the SDK replaces the requested scope with whatever the resource
    server advertises - for at least one well-known server, full mailbox control
    including permanent deletion.
    """
    source = inspect.getsource(PinnedScopeOAuthProvider._perform_authorization_code_grant)

    assert "client_metadata.scope = self._pinned_scope" in source


def test_the_pinned_scope_is_readable_for_an_operator() -> None:
    assert "pinned_scope" in inspect.signature(PinnedScopeOAuthProvider.__init__).parameters

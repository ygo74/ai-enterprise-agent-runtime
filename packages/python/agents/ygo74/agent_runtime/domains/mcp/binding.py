"""How a binding declares a server, and how one connection reaches it.

Two servers never expose the same surface. One may have no send tool, another no
per-item retrieval, and each will name its tools its own way. Rather than pretend
otherwise, a binding declares how to reach the server, which of an application's
capabilities it can actually serve, and the name it gives each tool.

Anything a server does not declare is simply not offered to the model, instead of
failing on the first call - which, for a gated operation, would mean failing
*after* somebody had already approved it.

The binding is generic over whatever an application uses to name its capabilities.
The library never interprets those names; it only checks that what a file declares
is among them.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Iterable, Mapping
from contextlib import AsyncExitStack
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Generic, TypeVar

from ygo74.agent_runtime.domains.mcp.mcp_errors import (
    McpBindingError,
    McpToolUnavailableError,
)

try:  # pragma: no cover - depends on the optional `mcp` extra
    import httpx
    import yaml
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client

    _MCP_AVAILABLE = True
    _MCP_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001  # pragma: no cover - the extra is optional by design
    httpx = None  # type: ignore[assignment]
    yaml = None  # type: ignore[assignment]
    ClientSession = Any  # type: ignore[assignment,misc]
    StdioServerParameters = Any  # type: ignore[assignment,misc]
    stdio_client = None  # type: ignore[assignment]
    streamablehttp_client = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False
    _MCP_IMPORT_ERROR = exc

CapabilityT = TypeVar("CapabilityT", bound=StrEnum)

DEFAULT_DIALECT = "native"
_PYTHON = "python"

_logger = logging.getLogger(__name__)


class McpTransport(StrEnum):
    """How a client reaches a server."""

    STDIO = "stdio"
    HTTP = "http"


class McpServerBinding(Generic[CapabilityT]):
    """What a deployed server offers, and how to reach it."""

    def __init__(
        self,
        *,
        server: str,
        transport: McpTransport,
        capabilities: Iterable[CapabilityT],
        tools: Mapping[str, str],
        dialect: str = DEFAULT_DIALECT,
        url: str = "",
        command: str = "",
        args: Iterable[str] = (),
        env: Mapping[str, str] | None = None,
        read_only_variable: str = "",
    ) -> None:
        self._server = server
        self._transport = transport
        self._capabilities = frozenset(capabilities)
        self._tools = dict(tools)
        self._dialect = dialect
        self._url = url
        self._command = command
        self._args = tuple(args)
        self._env = dict(env or {})
        self._read_only_variable = read_only_variable

    @property
    def server(self) -> str:
        """Name of the bound server."""
        return self._server

    @property
    def dialect(self) -> str:
        """Which client speaks to this server.

        ``native`` means the server answers the application's own tool names with
        its contract payloads and needs no translation.
        """
        return self._dialect

    @property
    def transport(self) -> McpTransport:
        """How the client reaches the server."""
        return self._transport

    @property
    def url(self) -> str:
        """Endpoint of an HTTP server."""
        return self._url

    @property
    def command(self) -> str:
        """Executable of a stdio server."""
        return self._command

    @property
    def args(self) -> tuple[str, ...]:
        """Arguments of a stdio server."""
        return self._args

    @property
    def env(self) -> Mapping[str, str]:
        """Extra environment handed to a stdio server."""
        return dict(self._env)

    @property
    def capabilities(self) -> frozenset[CapabilityT]:
        """Capabilities this server declares it can serve."""
        return self._capabilities

    @property
    def read_only_variable(self) -> str:
        """Environment variable deciding whether this server accepts writes.

        The *name* is schema; what to do about it is not. Withdrawing write
        capabilities when it is set is a decision about a deployment, and belongs
        to the application that made it.
        """
        return self._read_only_variable

    def supports(self, capability: CapabilityT) -> bool:
        """Whether the server declares it can serve a capability."""
        return capability in self._capabilities

    def remote(self, alias: str) -> str:
        """Return the name this server gives to a tool the dialect needs."""
        remote = self._tools.get(alias)
        if remote is None:
            raise McpBindingError(f"server {self._server!r} declares no tool named {alias!r}")
        return remote

    def require_aliases(self, aliases: Iterable[str]) -> None:
        """Fail now when the dialect needs a tool the binding never named."""
        missing = sorted(alias for alias in aliases if alias not in self._tools)
        if missing:
            raise McpBindingError(f"server {self._server!r} is missing tool names {missing}")

    def require_declared_capabilities(self) -> None:
        """Fail now when a declared capability has no tool behind it.

        A binding offering a capability without naming the tool that performs it
        would advertise it to the model and fail on the first call - after the
        user had already confirmed a write.
        """
        undeclared = sorted(
            str(capability.value) for capability in self._capabilities if str(capability.value) not in self._tools
        )
        if undeclared:
            raise McpBindingError(
                f"server {self._server!r} declares capabilities {undeclared} but names no tool for them"
            )


class McpServerBindingLoader(Generic[CapabilityT]):
    """Reads and validates a binding file.

    Args:
        capabilities: The enumeration naming what this application can ask for.
            A file may declare a subset of it and nothing else.

    Where the file *lives* is the host's business - a configuration directory, a
    package resource, a bucket - so a path is passed in rather than resolved here.
    """

    def __init__(self, capabilities: type[CapabilityT]) -> None:
        _require_mcp()
        self._capabilities = capabilities

    def load(self, path: Path, *, name: str = "") -> McpServerBinding[CapabilityT]:
        """Read the binding at ``path``."""
        document = self._document(path)
        binding: McpServerBinding[CapabilityT] = McpServerBinding(
            server=str(document.get("server", name or path.stem)),
            transport=self._transport(document, path),
            capabilities=self._declared(document, path),
            tools=self._tools(document, path),
            dialect=str(document.get("dialect", DEFAULT_DIALECT)).strip() or DEFAULT_DIALECT,
            url=str(document.get("url", "")).strip(),
            command=str(document.get("command", "")).strip(),
            args=tuple(str(item) for item in self._list(document, "args", path)),
            env=self._env(document, path),
            read_only_variable=str(document.get("read_only_variable", "")).strip(),
        )
        self._require_endpoint(binding, path)
        return binding

    @staticmethod
    def _document(path: Path) -> dict[str, Any]:
        """Parse the binding file, refusing anything but a mapping."""
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise McpBindingError(f"could not read {path}: {error}") from error
        if not isinstance(document, dict):
            raise McpBindingError(f"{path} must contain a mapping")
        return document

    @staticmethod
    def _transport(document: dict[str, Any], path: Path) -> McpTransport:
        """Return the declared transport."""
        declared = str(document.get("transport", "")).strip().lower()
        try:
            return McpTransport(declared)
        except ValueError as error:
            accepted = ", ".join(member.value for member in McpTransport)
            raise McpBindingError(f"{path}: 'transport' must be one of {accepted}, got {declared!r}") from error

    @staticmethod
    def _list(document: dict[str, Any], key: str, path: Path) -> list[Any]:
        """Return an optional list field."""
        value = document.get(key, [])
        if not isinstance(value, list):
            raise McpBindingError(f"{path}: field {key!r} must be a list")
        return value

    def _declared(self, document: dict[str, Any], path: Path) -> frozenset[CapabilityT]:
        """Return the catalogued capabilities the server declares."""
        declared = self._list(document, "capabilities", path)
        if not declared:
            raise McpBindingError(f"{path}: 'capabilities' must list at least one capability")
        known = {str(name.value): name for name in self._capabilities}
        unknown = sorted(str(item) for item in declared if str(item) not in known)
        if unknown:
            raise McpBindingError(f"{path}: unknown capabilities {unknown}")
        return frozenset(known[str(item)] for item in declared)

    @staticmethod
    def _tools(document: dict[str, Any], path: Path) -> dict[str, str]:
        """Return the alias-to-remote-name table."""
        tools = document.get("tools", {})
        if not isinstance(tools, dict):
            raise McpBindingError(f"{path}: field 'tools' must be a mapping")
        return {str(alias): str(remote) for alias, remote in tools.items()}

    @staticmethod
    def _env(document: dict[str, Any], path: Path) -> dict[str, str]:
        """Return the extra environment of a stdio server."""
        env = document.get("env", {})
        if not isinstance(env, dict):
            raise McpBindingError(f"{path}: field 'env' must be a mapping")
        return {str(key): str(value) for key, value in env.items()}

    @staticmethod
    def _require_endpoint(binding: McpServerBinding[CapabilityT], path: Path) -> None:
        """Refuse a binding that names no way to reach its server."""
        if binding.transport is McpTransport.HTTP and not binding.url:
            raise McpBindingError(f"{path}: an http binding needs a 'url'")
        if binding.transport is McpTransport.STDIO and not binding.command:
            raise McpBindingError(f"{path}: a stdio binding needs a 'command'")


class McpConnection:
    """Holds one client session, opened on first use.

    One session, and exactly one. A model routinely calls two tools in the same
    turn, and a framework runs them concurrently. Without a guard each of them
    opens its own transport; the losers are then garbage collected from whichever
    task happens to run last, and anyio refuses to unwind a cancel scope outside
    the task that entered it. The visible symptom is not a warning: the transport
    dies mid-turn and the system appears to be unavailable.

    Opening a session per call would instead pay the initialisation handshake -
    and, over HTTP, a token exchange - on every message the user reads.
    """

    def __init__(
        self,
        binding: McpServerBinding[Any],
        *,
        timeout_seconds: int = 30,
        auth: Any | None = None,
        unavailable: type[McpToolUnavailableError] = McpToolUnavailableError,
    ) -> None:
        _require_mcp()
        self._binding = binding
        self._timeout = timeout_seconds
        self._auth = auth
        self._unavailable = unavailable
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._opening = asyncio.Lock()

    async def session(self) -> ClientSession:
        """Return the open session, connecting the first time it is needed.

        The check is repeated inside the lock: several callers can pass the first
        one together, and only the first through the door may connect.
        """
        if self._session is not None:
            return self._session
        async with self._opening:
            if self._session is None:
                self._session = await self._connect()
            return self._session

    async def aclose(self) -> None:
        """Close the session and release the transport."""
        stack, self._stack, self._session = self._stack, None, None
        if stack is None:
            return
        try:
            await stack.aclose()
        except (OSError, RuntimeError, *_http_errors()) as error:
            # The conversation is over; a server that already went away must not
            # turn a clean exit into a crash.
            _logger.debug("connection was already unavailable while closing: %s", type(error).__name__)
            return

    async def _connect(self) -> ClientSession:
        """Open the transport and initialise the protocol session."""
        stack = AsyncExitStack()
        try:
            session = await self._open(stack)
            await session.initialize()
        except Exception as error:
            _logger.warning(
                "connection failed: server=%s transport=%s error=%s",
                self._binding.server,
                self._binding.transport.value,
                type(error).__name__,
            )
            await stack.aclose()
            raise self._unavailable(
                f"MCP server {self._binding.server!r} could not be reached: {type(error).__name__}"
            ) from error
        self._stack = stack
        return session

    async def _open(self, stack: AsyncExitStack) -> ClientSession:
        """Open the transport the binding asks for."""
        if self._binding.transport is McpTransport.HTTP:
            read, write, _ = await stack.enter_async_context(
                streamablehttp_client(self._binding.url, timeout=self._timeout, auth=self._auth)
            )
        else:
            read, write = await stack.enter_async_context(stdio_client(self._stdio_parameters()))
        return await stack.enter_async_context(
            ClientSession(read, write, read_timeout_seconds=timedelta(seconds=self._timeout))
        )

    def _stdio_parameters(self) -> StdioServerParameters:
        """Describe the process to start for a stdio server.

        ``python`` is resolved to the interpreter currently running, so a server
        declared in configuration starts in this virtual environment rather than
        in whatever happens to be first on the PATH.
        """
        command = self._binding.command
        return StdioServerParameters(
            command=sys.executable if command == _PYTHON else command,
            args=list(self._binding.args),
            env=dict(self._binding.env) or None,
        )


def _http_errors() -> tuple[type[BaseException], ...]:
    """The transport errors worth tolerating while closing."""
    return (httpx.HTTPError,) if httpx is not None else ()


def _require_mcp() -> None:
    """Fail with the reason rather than an import error three frames down."""
    if not _MCP_AVAILABLE:
        raise RuntimeError(
            "the 'mcp' extra of ygo74-agent-runtime is required to reach a Model Context Protocol server"
        ) from _MCP_IMPORT_ERROR

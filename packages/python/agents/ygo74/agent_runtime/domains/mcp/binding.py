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
import json
import logging
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar
from urllib.parse import urlsplit

from ygo74.agent_runtime.domains.auth.oauth_token_exchange import (
    OAuthTokenExchangeSettings,
    Rfc8693OAuthOnBehalfOfTokenSource,
)
from ygo74.agent_runtime.domains.auth.tokens import (
    OAuthOnBehalfOfTokenSource,
    TokenExchangeError,
)
from ygo74.agent_runtime.domains.configuration.manifest_schemas import (
    JsonSchemaValidator,
    ManifestSchemas,
)
from ygo74.agent_runtime.domains.http.client_lifecycle import (
    HttpxTransportFailureClassifier,
    RetryableHttpStatusError,
)
from ygo74.agent_runtime.domains.http.resilience import (
    DEFAULT_CIRCUIT_BREAKERS,
    CircuitBreakerSettings,
    RetryExecutor,
    RetrySettings,
    ServiceCircuitBreakerRegistry,
)
from ygo74.agent_runtime.domains.mcp.mcp_errors import (
    McpBindingError,
    McpToolUnavailableError,
)

if TYPE_CHECKING:
    from ygo74.agent_runtime.domains.contracts.invocation_context import (
        AgentInvocationContext,
    )

try:  # pragma: no cover - depends on the optional `mcp` extra
    import httpx
    import yaml
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    _MCP_AVAILABLE = True
    _MCP_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001  # pragma: no cover - the extra is optional by design
    httpx = None  # type: ignore[assignment]
    yaml = None  # type: ignore[assignment]
    ClientSession = Any  # type: ignore[assignment,misc]
    StdioServerParameters = Any  # type: ignore[assignment,misc]
    stdio_client = None  # type: ignore[assignment]
    streamable_http_client = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False
    _MCP_IMPORT_ERROR = exc

CapabilityT = TypeVar("CapabilityT", bound=StrEnum)
ErrorFactory = Callable[[str], Exception]

DEFAULT_DIALECT = "native"
_PYTHON = "python"

_logger = logging.getLogger(__name__)
_current_http_context: ContextVar[tuple[Any, Any] | None] = ContextVar(
    "agent_runtime_mcp_http_context", default=None
)
_MCP_TRANSPORT_HEADERS = frozenset(
    {"accept", "content-type", "mcp-session-id", "mcp-protocol-version", "last-event-id"}
)


class _RedactedMapping(Mapping[str, str]):
    """Read-only sensitive string values whose representation contains keys only.

    Args:
        values (Mapping[str, str]): Candidate values read from the source mapping.
    """

    def __init__(self, values: Mapping[str, str]) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            values (Mapping[str, str]): Candidate values read from the source mapping.
        """
        self._values = dict(values)

    def __getitem__(self, key: str) -> str:
        """Read a header using case-insensitive lookup semantics.

        Args:
            key (str): The identifier used to locate the corresponding registered value.
        """
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        """Iterate over registered entries runtime data in their documented deterministic order."""
        return iter(self._values)

    def __len__(self) -> int:
        """Return the number of registered entries runtime data without exposing the backing collection."""
        return len(self._values)

    def __repr__(self) -> str:
        """Return a safe representation that does not expose credential values."""
        return f"{type(self).__name__}(keys={tuple(sorted(self._values))!r})"

    def __eq__(self, other: object) -> bool:
        """Compare bindings using their normalized header and transport configuration.

        Args:
            other (object): Fallback value used when no specialized case matches.
        """
        return isinstance(other, Mapping) and self._values == dict(other)


class McpTransport(StrEnum):
    """How a client reaches a server."""

    STDIO = "stdio"
    HTTP = "http"


@dataclass(frozen=True, slots=True, repr=False)
class McpNetworkSettings:
    """HTTP network settings shared by a server binding's connections.

    Args:
        proxy_url (str | None): Optional credential-free HTTP or HTTPS proxy URL.
        max_connections (int): Maximum simultaneous connections in this server pool.
        max_keepalive_connections (int): Maximum reusable idle connections in the pool.
    """

    proxy_url: str | None = field(default=None, repr=False)
    max_connections: int = 20
    max_keepalive_connections: int = 10

    def __post_init__(self) -> None:
        """Reject proxy URLs that cannot safely be represented or used."""
        if self.max_connections < 1:
            raise ValueError("network.max_connections must be at least 1")
        if not 0 <= self.max_keepalive_connections <= self.max_connections:
            raise ValueError(
                "network.max_keepalive_connections must be between 0 and network.max_connections"
            )
        if self.proxy_url is None:
            return
        parsed = urlsplit(self.proxy_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError(
                "network.proxy_url must be a credential-free HTTP or HTTPS URL"
            )
        try:
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError("network.proxy_url port is outside the valid range")
        except ValueError as error:
            if "network.proxy_url" in str(error):
                raise
            raise ValueError("network.proxy_url has an invalid port") from error

    def __repr__(self) -> str:
        """Describe proxy presence without printing its address or credentials."""
        return (
            f"{type(self).__name__}(proxy_configured={self.proxy_url is not None}, "
            f"max_connections={self.max_connections!r}, "
            f"max_keepalive_connections={self.max_keepalive_connections!r})"
        )


class McpServerBinding(Generic[CapabilityT]):
    """What a deployed server offers, and how to reach it.

    Args:
        server (str): MCP server instance receiving the registered routes.
        transport (McpTransport): MCP transport implementation selected for this host.
        capabilities (Iterable[CapabilityT]): Declared agent capabilities checked against exposed endpoints.
        tools (Mapping[str, str]): Declared tools exposed by the MCP server.
        dialect (str): Provider wire dialect selected for this discovery response.
        url (str): Absolute URL associated with a citation or remote resource.
        command (str): Requested operation that must pass the authorization gate.
        args (Iterable[str]): Positional arguments forwarded to the wrapped function.
        env (Mapping[str, str] | None): Environment-variable mapping used instead of the process environment.
        read_only_variable (str): Environment variable that must not be changed by this operation.
        error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
    """

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
        error_factory: ErrorFactory = McpBindingError,
    ) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            server (str): MCP server instance receiving the registered routes.
            transport (McpTransport): MCP transport implementation selected for this host.
            capabilities (Iterable[CapabilityT]): Declared agent capabilities checked against exposed endpoints.
            tools (Mapping[str, str]): Declared tools exposed by the MCP server.
            dialect (str): Provider wire dialect selected for this discovery response.
            url (str): Absolute URL associated with a citation or remote resource.
            command (str): Requested operation that must pass the authorization gate.
            args (Iterable[str]): Positional arguments forwarded to the wrapped function.
            env (Mapping[str, str] | None): Environment-variable mapping used instead of the process environment.
            read_only_variable (str): Environment variable that must not be changed by this operation.
            error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
        """
        self._server = server
        self._transport = transport
        self._capabilities = frozenset(capabilities)
        self._tools = dict(tools)
        self._dialect = dialect
        self._url = url
        self._command = command
        self._args = tuple(args)
        self._env = _RedactedMapping(env or {})
        self._read_only_variable = read_only_variable
        self._error_factory = error_factory

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
        return self._env

    @property
    def tools(self) -> Mapping[str, str]:
        """Application aliases and the remote names a server assigns them."""
        return dict(self._tools)

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
        """Whether the server declares it can serve a capability.

        Args:
            capability (CapabilityT): Capability declaration checked against the runtime configuration.
        """
        return capability in self._capabilities

    def remote(self, alias: str) -> str:
        """Return the name this server gives to a tool the dialect needs.

        Args:
            alias (str): Alias registered for an agent, route, or environment setting.
        """
        remote = self._tools.get(alias)
        if remote is None:
            raise self._error_factory(
                f"server {self._server!r} declares no tool named {alias!r}"
            )
        return remote

    def require_aliases(self, aliases: Iterable[str]) -> None:
        """Fail now when the dialect needs a tool the binding never named.

        Args:
            aliases (Iterable[str]): Aliases accepted for the configured agent or setting.
        """
        missing = sorted(alias for alias in aliases if alias not in self._tools)
        if missing:
            raise self._error_factory(
                f"server {self._server!r} is missing tool names {missing}"
            )

    def require_declared_capabilities(self) -> None:
        """Fail now when a declared capability has no tool behind it.

        A binding offering a capability without naming the tool that performs it
        would advertise it to the model and fail on the first call - after the
        user had already confirmed a write.
        """
        undeclared = sorted(
            str(capability.value)
            for capability in self._capabilities
            if str(capability.value) not in self._tools
        )
        if undeclared:
            raise self._error_factory(
                f"server {self._server!r} declares capabilities {undeclared} but names no tool for them"
            )


class McpServerBindingLoader(Generic[CapabilityT]):
    """Reads and validates a binding file.

    Args:
        capabilities: The enumeration naming what this application can ask for.
            A file may declare a subset of it and nothing else.

        error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
    Where the file *lives* is the host's business - a configuration directory, a
    package resource, a bucket - so a path is passed in rather than resolved here.
    """

    def __init__(
        self,
        capabilities: type[CapabilityT],
        *,
        error_factory: ErrorFactory = McpBindingError,
    ) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            capabilities (type[CapabilityT]): Declared agent capabilities checked against exposed endpoints.
            error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
        """
        _require_mcp()
        self._capabilities = capabilities
        self._error_factory = error_factory

    def load(self, path: Path, *, name: str = "") -> McpServerBinding[CapabilityT]:
        """Read the binding at ``path``.

        Args:
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
            name (str): The name used to locate or label the value.
        """
        document = self._document(path)
        binding: McpServerBinding[CapabilityT] = McpServerBinding(
            server=str(document.get("server", name or path.stem)),
            transport=self._transport(document, path),
            capabilities=self._declared(document, path),
            tools=self._tools(document, path),
            dialect=str(document.get("dialect", DEFAULT_DIALECT)).strip()
            or DEFAULT_DIALECT,
            url=str(document.get("url", "")).strip(),
            command=str(document.get("command", "")).strip(),
            args=tuple(str(item) for item in self._list(document, "args", path)),
            env=self._env(document, path),
            read_only_variable=str(document.get("read_only_variable", "")).strip(),
            error_factory=self._error_factory,
        )
        self._require_endpoint(binding, path)
        return binding

    def _document(self, path: Path) -> dict[str, Any]:
        """Parse the binding file, refusing anything but a mapping.

        Args:
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise self._error_factory(f"could not read {path}: {error}") from error
        if not isinstance(document, dict):
            raise self._error_factory(f"{path} must contain a mapping")
        try:
            JsonSchemaValidator.validate(
                document, ManifestSchemas.mcp_server(), path=path
            )
        except ValueError as error:
            raise self._error_factory(str(error)) from error
        return document

    def _transport(self, document: dict[str, Any], path: Path) -> McpTransport:
        """Return the declared transport.

        Args:
            document (dict[str, Any]): Manifest or descriptor document being parsed and validated.
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        declared = str(document.get("transport", "")).strip().lower()
        try:
            return McpTransport(declared)
        except ValueError as error:
            accepted = ", ".join(member.value for member in McpTransport)
            raise self._error_factory(
                f"{path}: 'transport' must be one of {accepted}, got {declared!r}"
            ) from error

    def _list(self, document: dict[str, Any], key: str, path: Path) -> list[Any]:
        """Return an optional list field.

        Args:
            document (dict[str, Any]): Manifest or descriptor document being parsed and validated.
            key (str): The identifier used to locate the corresponding registered value.
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        value = document.get(key, [])
        if not isinstance(value, list):
            raise self._error_factory(f"{path}: field {key!r} must be a list")
        return value

    def _declared(self, document: dict[str, Any], path: Path) -> frozenset[CapabilityT]:
        """Return the catalogued capabilities the server declares.

        Args:
            document (dict[str, Any]): Manifest or descriptor document being parsed and validated.
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        declared = self._list(document, "capabilities", path)
        if not declared:
            raise self._error_factory(
                f"{path}: 'capabilities' must list at least one capability"
            )
        known = {str(name.value): name for name in self._capabilities}
        unknown = sorted(str(item) for item in declared if str(item) not in known)
        if unknown:
            raise self._error_factory(f"{path}: unknown capabilities {unknown}")
        return frozenset(known[str(item)] for item in declared)

    def _tools(self, document: dict[str, Any], path: Path) -> dict[str, str]:
        """Return the alias-to-remote-name table.

        Args:
            document (dict[str, Any]): Manifest or descriptor document being parsed and validated.
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        tools = document.get("tools", {})
        if not isinstance(tools, dict):
            raise self._error_factory(f"{path}: field 'tools' must be a mapping")
        return {str(alias): str(remote) for alias, remote in tools.items()}

    def _env(self, document: dict[str, Any], path: Path) -> dict[str, str]:
        """Return the extra environment of a stdio server.

        Args:
            document (dict[str, Any]): Manifest or descriptor document being parsed and validated.
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        env = document.get("env", {})
        if not isinstance(env, dict):
            raise self._error_factory(f"{path}: field 'env' must be a mapping")
        return {str(key): str(value) for key, value in env.items()}

    def _require_endpoint(
        self, binding: McpServerBinding[CapabilityT], path: Path
    ) -> None:
        """Refuse a binding that names no way to reach its server.

        Args:
            binding (McpServerBinding[CapabilityT]): MCP transport binding and its authentication metadata.
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        if binding.transport is McpTransport.HTTP and not binding.url:
            raise self._error_factory(f"{path}: an http server requires 'url'")
        if binding.transport is McpTransport.STDIO and not binding.command:
            raise self._error_factory(f"{path}: a stdio server requires 'command'")


@dataclass(slots=True)
class _McpConnectionSession:
    """Own one MCP transport, its request contexts, and its opening lock."""

    stack: AsyncExitStack | None = None
    session: Any | None = None
    contexts: Any | None = None
    context: AgentInvocationContext | None = None
    opening: asyncio.Lock = field(default_factory=asyncio.Lock)


class McpConnection:
    """Holds lazy client sessions, partitioned by caller when using OBO.

    Each session is guarded so concurrent tool calls from one principal reuse
    the transport. OBO callers never share a session or its long-lived SSE stream.

    Args:
        binding (McpServerBinding[Any]): MCP transport binding and its authentication metadata.
        timeout_seconds (int): Maximum duration allowed for the operation.
        auth (Any | None): Authentication configuration used by the protected MCP resource.
        headers (Mapping[str, str] | None): The request headers used for protocol selection, forwarding, or authentication.
        network (McpNetworkSettings | None): HTTP proxy configuration for this connection.
        unavailable (ErrorFactory): Response or fallback used when the underlying service is unavailable.
        delegated_oauth (OAuthTokenExchangeSettings | None): Downstream audience and scopes for OBO mode.
        delegated_token_source (OAuthOnBehalfOfTokenSource | None): Application-owned provider exchange implementation.
        retry_settings (RetrySettings): Bounded policy for safe HTTP operations.
        circuit_breaker_settings (CircuitBreakerSettings): Policy for the remote service circuit.
        breaker_registry (ServiceCircuitBreakerRegistry): Shared service-scoped breaker state.
    """

    def __init__(
        self,
        binding: McpServerBinding[Any],
        *,
        timeout_seconds: int = 30,
        auth: Any | None = None,
        headers: Mapping[str, str] | None = None,
        network: McpNetworkSettings | None = None,
        delegated_oauth: OAuthTokenExchangeSettings | None = None,
        delegated_token_source: OAuthOnBehalfOfTokenSource | None = None,
        retry_settings: RetrySettings | None = None,
        circuit_breaker_settings: CircuitBreakerSettings | None = None,
        breaker_registry: ServiceCircuitBreakerRegistry = DEFAULT_CIRCUIT_BREAKERS,
        unavailable: ErrorFactory = McpToolUnavailableError,
    ) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            binding (McpServerBinding[Any]): MCP transport binding and its authentication metadata.
            timeout_seconds (int): Maximum duration allowed for the operation.
            auth (Any | None): Authentication configuration used by the protected MCP resource.
            headers (Mapping[str, str] | None): The request headers used for protocol selection, forwarding, or authentication.
            network (McpNetworkSettings | None): HTTP proxy configuration for this connection.
            delegated_oauth (OAuthTokenExchangeSettings | None): Downstream audience and scopes for OBO mode.
            delegated_token_source (OAuthOnBehalfOfTokenSource | None): Application-owned provider exchange implementation.
            retry_settings (RetrySettings | None): Bounded retry policy for safe HTTP operations.
            circuit_breaker_settings (CircuitBreakerSettings | None): Remote service circuit policy.
            breaker_registry (ServiceCircuitBreakerRegistry): Shared upstream breaker state.
            unavailable (ErrorFactory): Response or fallback used when the underlying service is unavailable.
        """
        _require_mcp()
        self._binding = binding
        self._timeout = timeout_seconds
        self._auth = auth
        self._headers = _RedactedMapping(headers or {})
        self._network = network or McpNetworkSettings()
        self._delegated_oauth = delegated_oauth
        self._delegated_token_source = delegated_token_source
        self._retry_settings = retry_settings or RetrySettings()
        self._circuit_breaker_settings = (
            circuit_breaker_settings or CircuitBreakerSettings()
        )
        self._breaker_registry = breaker_registry
        self._unavailable = unavailable
        self._sessions: dict[str | None, _McpConnectionSession] = {}
        self._http_client: Any | None = None
        if (
            delegated_oauth is not None
            and delegated_token_source is None
            and delegated_oauth.token_url is not None
            and delegated_oauth.client_id is not None
            and delegated_oauth.client_secret is not None
        ):
            self._delegated_token_source = Rfc8693OAuthOnBehalfOfTokenSource(
                delegated_oauth,
                client_provider=self._get_http_client,
                retry_settings=self._retry_settings,
                breaker_settings=self._circuit_breaker_settings,
                breaker_registry=self._breaker_registry,
            )

    async def session(self) -> ClientSession:
        """Return the current caller's session, opening it on first use.

        OBO requires a verified principal and subject token. Its sessions are
        keyed by principal subject; other modes retain one shared session. The
        session identity context omits turn metadata that cannot be correlated to
        the long-lived SSE stream.
        """
        from ygo74.agent_runtime.domains.contracts.invocation_context import (
            AgentInvocationContext,
            AgentInvocationContextScope,
        )

        context = AgentInvocationContextScope.current()
        principal_key: str | None = None
        session_context: AgentInvocationContext | None = None
        if self._delegated_oauth is not None:
            if context is None or context.principal is None or context.subject_token is None:
                raise TokenExchangeError(
                    "delegated session requires an authenticated caller token"
                )
            principal_key = context.principal.subject
            session_context = AgentInvocationContext(
                principal=context.principal,
                subject_token=context.subject_token,
            )

        state = self._sessions.setdefault(principal_key, _McpConnectionSession())
        if session_context is not None:
            state.context = session_context
            if state.contexts is not None:
                state.contexts.set_session_context(session_context)
        if state.session is not None:
            return state.session
        async with state.opening:
            if state.session is None:
                state.session = await self._connect(state, session_context)
            return state.session

    async def aclose(self) -> None:
        """Close every principal's session and release all transports."""
        states, self._sessions = tuple(self._sessions.values()), {}
        close_error: Exception | None = None
        for state in states:
            if state.contexts is not None:
                state.contexts.clear()
                state.contexts = None
            stack, state.stack, state.session = state.stack, None, None
            state.context = None
            if stack is None:
                continue
            try:
                await stack.aclose()
            except Exception as error:  # noqa: BLE001 - close remaining sessions before re-raising.
                if _is_connection_close_error(error):
                    _logger.debug(
                        "connection was already unavailable while closing: %s",
                        type(error).__name__,
                    )
                elif close_error is None:
                    close_error = error
        client, self._http_client = self._http_client, None
        if client is not None:
            try:
                await client.aclose()
            except Exception as error:  # noqa: BLE001 - release the pool after all session cleanup attempts.
                if close_error is None:
                    close_error = error
        if close_error is not None:
            raise close_error

    async def _connect(
        self,
        state: _McpConnectionSession,
        context: AgentInvocationContext | None,
    ) -> ClientSession:
        """Open the transport and initialise the protocol session."""
        stack = AsyncExitStack()
        try:
            state.context = context
            session = await self._open(stack, state)
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
        state.stack = stack
        return session

    async def _open(
        self, stack: AsyncExitStack, state: _McpConnectionSession
    ) -> ClientSession:
        """Open the transport the binding asks for.

        Args:
            stack (AsyncExitStack): Ordered middleware or execution stack.
        """
        if self._binding.transport is McpTransport.HTTP:
            from ygo74.agent_runtime.domains.contracts.invocation_context import (
                AgentInvocationContextScope,
            )
            from ygo74.agent_runtime.domains.mcp.request_context import (
                McpOutboundHeaderResolver,
                McpRequestContextRegistry,
                json_rpc_request_id,
            )

            contexts = McpRequestContextRegistry()
            state.contexts = contexts
            if state.context is not None:
                contexts.set_session_context(state.context)
            resolver = McpOutboundHeaderResolver(
                self._headers,
                contexts,
                delegated_oauth=self._delegated_oauth,
                delegated_token_source=self._delegated_token_source,
                error_factory=self._unavailable,
            )
            context_token = _current_http_context.set((resolver, contexts))
            try:
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(
                        self._binding.url,
                        http_client=self._get_http_client(),
                    )
                )
            finally:
                # The SDK's transport tasks inherit this session-specific context
                # when they are created, while other OBO sessions remain isolated.
                _current_http_context.reset(context_token)
            write = _ContextualMcpWriteStream(
                write,
                contexts,
                AgentInvocationContextScope.current,
                request_id_for_message=json_rpc_request_id,
            )
        else:
            read, write = await stack.enter_async_context(
                stdio_client(self._stdio_parameters())
            )
        return await stack.enter_async_context(
            ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=self._timeout)
            )
        )

    def _get_http_client(self) -> Any:
        """Create and return this connection's one lazy asynchronous HTTP pool."""
        if self._binding.transport is not McpTransport.HTTP:
            raise RuntimeError("stdio MCP connections do not have an HTTP client")
        if self._http_client is not None:
            return self._http_client
        if httpx is None:
            raise RuntimeError("HTTP MCP connections require the 'mcp' extra")

        limits = httpx.Limits(
            max_connections=self._network.max_connections,
            max_keepalive_connections=self._network.max_keepalive_connections,
        )
        underlying = httpx.AsyncHTTPTransport(
            proxy=self._network.proxy_url,
            limits=limits,
            verify=True,
        )
        transport = _McpResilientTransport(
            underlying,
            service_identity=self._binding.url.rstrip("/"),
            retry_settings=self._retry_settings,
            breaker_settings=self._circuit_breaker_settings,
            breaker_registry=self._breaker_registry,
            timeout_seconds=float(self._timeout),
        )
        self._http_client = httpx.AsyncClient(
            transport=transport,
            auth=self._auth,
            timeout=httpx.Timeout(self._timeout, read=max(self._timeout, 300.0)),
            event_hooks={"request": [self._apply_request_headers]},
            verify=True,
        )
        return self._http_client

    async def _apply_request_headers(self, request: Any) -> None:
        """Add configured headers only to this server's correlated MCP requests."""
        if request.extensions.get("ygo74_skip_mcp_context"):
            return
        if not self._is_mcp_endpoint(request.url):
            return
        active = _current_http_context.get()
        if active is None:
            return
        resolver, _contexts = active
        if request.method == "POST":
            try:
                payload = json.loads(request.content)
            except (UnicodeDecodeError, ValueError):
                return
            if isinstance(payload, dict) and isinstance(
                payload.get("id"), (str, int)
            ):
                headers = await resolver.for_request(payload["id"])
            else:
                headers = await resolver.for_session()
        else:
            headers = await resolver.for_session()
        for name, value in headers.items():
            if name.casefold() not in _MCP_TRANSPORT_HEADERS:
                request.headers[name] = value

    def _is_mcp_endpoint(self, request_url: Any) -> bool:
        """Compare scheme, host, and port so auth-server calls get no MCP headers."""
        configured = urlsplit(self._binding.url)
        actual = urlsplit(str(request_url))
        return (
            actual.scheme.casefold(),
            (actual.hostname or "").casefold(),
            actual.port,
        ) == (
            configured.scheme.casefold(),
            (configured.hostname or "").casefold(),
            configured.port,
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


def _is_connection_close_error(error: Exception) -> bool:
    """Whether an error means the remote transport was already unavailable.

    Args:
        error (Exception): Structured error associated with a failed operation.
    """
    if isinstance(error, (OSError, RuntimeError)):
        return True
    return httpx is not None and isinstance(error, httpx.HTTPError)


def _require_mcp() -> None:
    """Fail with the reason rather than an import error three frames down."""
    if not _MCP_AVAILABLE:
        raise RuntimeError(
            "the 'mcp' extra of ygo74-agent-runtime is required to reach a Model Context Protocol server"
        ) from _MCP_IMPORT_ERROR


_AsyncTransportBase = httpx.AsyncBaseTransport if httpx is not None else object


class _McpResilientTransport(_AsyncTransportBase):
    """Apply per-service breaker and safe-request retries below the HTTPX client.

    Args:
        transport (Any): HTTPX transport owning the one server connection pool.
        service_identity (str): Stable MCP endpoint identity for breaker sharing.
        retry_settings (RetrySettings): Bounded retry policy for setup requests.
        breaker_settings (CircuitBreakerSettings): Threshold and cooldown.
        breaker_registry (ServiceCircuitBreakerRegistry): Shared service states.
        timeout_seconds (float): Total deadline for a retry sequence.
    """

    _RETRYABLE_STATUSES = frozenset({500, 502, 503, 504})
    _SAFE_POST_METHODS = frozenset({"initialize", "ping"})

    def __init__(
        self,
        transport: Any,
        *,
        service_identity: str,
        retry_settings: RetrySettings,
        breaker_settings: CircuitBreakerSettings,
        breaker_registry: ServiceCircuitBreakerRegistry,
        timeout_seconds: float,
    ) -> None:
        """Retain the underlying pool and resilience policy for this MCP server."""
        self._transport = transport
        self._service_identity = service_identity
        self._retry_settings = retry_settings
        self._breaker_settings = breaker_settings
        self._breaker_registry = breaker_registry
        self._timeout_seconds = timeout_seconds

    async def handle_async_request(self, request: Any) -> Any:
        """Send one request, retrying only safe setup/read requests."""
        if httpx is None:
            raise RuntimeError("HTTPX is required for the MCP transport")
        if request.extensions.get("ygo74_skip_runtime_resilience") or not self._is_mcp_origin(request):
            return await self._transport.handle_async_request(request)

        identity = self._service_identity
        breaker = self._breaker_registry.for_service(
            identity, self._breaker_settings
        )
        breaker.before_call()

        safe_to_retry = self._is_safe_request(request)
        body = await request.aread() if safe_to_retry else b""
        try:
            if safe_to_retry:
                response = await RetryExecutor.run_async(
                    lambda remaining: self._send(
                        request,
                        body,
                        timeout_seconds=remaining,
                        retry_transient_status=True,
                    ),
                    settings=self._retry_settings,
                    timeout_seconds=self._timeout_seconds,
                    retryable_exceptions=(
                        *HttpxTransportFailureClassifier.retryable_exception_types(
                            httpx
                        ),
                        RetryableHttpStatusError,
                    ),
                )
            else:
                response = await self._transport.handle_async_request(request)
        except Exception as error:
            if self._is_service_failure(error):
                breaker.record_failure()
            else:
                breaker.record_success()
            raise
        if response.status_code >= 500:
            breaker.record_failure()
        else:
            breaker.record_success()
        return response

    async def aclose(self) -> None:
        """Close the owned HTTP transport and its connection pool."""
        await self._transport.aclose()

    async def _send(
        self,
        request: Any,
        body: bytes,
        *,
        timeout_seconds: float,
        retry_transient_status: bool,
    ) -> Any:
        """Send a replayable request with an attempt timeout capped to its deadline."""
        extensions = dict(request.extensions)
        timeouts = extensions.get("timeout")
        if isinstance(timeouts, dict):
            extensions["timeout"] = {
                phase: min(value, timeout_seconds)
                if isinstance(value, (float, int))
                else value
                for phase, value in timeouts.items()
            }
        retry_request = httpx.Request(
            request.method,
            request.url,
            headers=request.headers,
            content=body,
            extensions=extensions,
        )
        response = await self._transport.handle_async_request(retry_request)
        if retry_transient_status and response.status_code in self._RETRYABLE_STATUSES:
            status = response.status_code
            await response.aclose()
            raise RetryableHttpStatusError(status)
        return response

    def _is_safe_request(self, request: Any) -> bool:
        """Allow GET reads and only idempotent MCP initialization POST methods."""
        if request.method == "GET":
            return True
        if request.method != "POST":
            return False
        try:
            payload = json.loads(request.content)
        except (UnicodeDecodeError, ValueError):
            return False
        return (
            isinstance(payload, dict)
            and payload.get("method") in self._SAFE_POST_METHODS
        )

    def _is_mcp_origin(self, request: Any) -> bool:
        """Keep auth-server traffic outside this MCP endpoint's breaker state."""
        actual = urlsplit(str(request.url))
        configured = urlsplit(self._service_identity)
        return (
            actual.scheme.casefold(),
            (actual.hostname or "").casefold(),
            actual.port,
        ) == (
            configured.scheme.casefold(),
            (configured.hostname or "").casefold(),
            configured.port,
        )

    @staticmethod
    def _is_service_failure(error: Exception) -> bool:
        """Count transport loss and transient upstream responses as breaker failures."""
        return (
            isinstance(error, TimeoutError)
            or
            (
                httpx is not None
                and isinstance(
                    error,
                    HttpxTransportFailureClassifier.retryable_exception_types(httpx),
                )
            )
            or isinstance(error, RetryableHttpStatusError)
        )


class _ProxyHttpClientFactory:
    """Create the pinned MCP SDK's owned HTTP client with a configured proxy.

    Args:
        proxy_url (str): Credential-free HTTP or HTTPS proxy URL.
    """

    def __init__(self, proxy_url: str) -> None:
        """Initialize the factory with a prevalidated proxy URL.

        Args:
            proxy_url (str): Credential-free HTTP or HTTPS proxy URL.
        """
        self._proxy_url = proxy_url

    def __call__(
        self,
        headers: dict[str, str] | None = None,
        timeout: Any = None,
        auth: Any = None,
    ) -> Any:
        """Create an HTTPX client; the SDK owns and closes its lifetime.

        Args:
            headers (dict[str, str] | None): Default HTTP headers supplied by MCP.
            timeout (Any): HTTPX timeout selected by the MCP transport.
            auth (Any): HTTPX authentication handler supplied by MCP.
        """
        if httpx is None:
            raise RuntimeError("HTTP proxy support requires the 'mcp' extra")
        return httpx.AsyncClient(
            proxy=self._proxy_url,
            headers=headers,
            timeout=timeout,
            auth=auth,
        )


class _ContextualMcpWriteStream:
    """Register the active agent context before forwarding each JSON-RPC message.

    Args:
        stream (Any): SDK-owned asynchronous message stream.
        contexts (Any): Connection-local registry keyed by JSON-RPC request ID.
        current_context (Callable[[], Any]): Returns the request context inherited by this task.
        request_id_for_message (Callable[[Any], str | int | None]): Extracts the JSON-RPC ID from an SDK message.
    """

    def __init__(
        self,
        stream: Any,
        contexts: Any,
        current_context: Callable[[], Any],
        request_id_for_message: Callable[[Any], str | int | None],
    ) -> None:
        """Retain the SDK stream and the request correlation collaborators.

        Args:
            stream (Any): SDK-owned asynchronous message stream.
            contexts (Any): Connection-local registry keyed by JSON-RPC request ID.
            current_context (Callable[[], Any]): Returns the request context inherited by this task.
            request_id_for_message (Callable[[Any], str | int | None]): Extracts the JSON-RPC ID from an SDK message.
        """
        self._stream = stream
        self._contexts = contexts
        self._current_context = current_context
        self._request_id_for_message = request_id_for_message

    async def __aenter__(self) -> Self:
        """Enter the SDK stream while retaining request-context interception."""
        await self._stream.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Delegate SDK stream cleanup and exception handling.

        Args:
            exc_type (type[BaseException] | None): Exception type on session exit.
            exc_value (BaseException | None): Exception raised by the session.
            traceback (TracebackType | None): Traceback associated with the error.
        """
        return await self._stream.__aexit__(exc_type, exc_value, traceback)

    async def send(self, message: Any) -> None:
        """Associate a request's current turn before the persistent writer task receives it.

        Args:
            message (Any): MCP SDK session message sent to the transport.
        """
        request_id = self._request_id_for_message(message)
        context = self._current_context()
        if request_id is not None and context is not None:
            self._contexts.register(request_id, context)
        try:
            await self._stream.send(message)
        except BaseException:
            if request_id is not None:
                self._contexts.discard(request_id)
            raise

    def __getattr__(self, name: str) -> Any:
        """Delegate non-send stream operations to the SDK-owned stream.

        Args:
            name (str): Attribute requested by the MCP SDK session implementation.
        """
        return getattr(self._stream, name)


class _McpHttpClientFactory:
    """Create an MCP HTTP client with request-ID-correlated header injection.

    Args:
        network (McpNetworkSettings): Optional proxy setting for the HTTP client.
        resolver (Any): Renders headers and obtains OBO tokens per JSON-RPC request.
    """

    _TRANSPORT_HEADERS = frozenset(
        {
            "accept",
            "content-type",
            "mcp-session-id",
            "mcp-protocol-version",
            "last-event-id",
        }
    )

    def __init__(self, network: McpNetworkSettings, resolver: Any) -> None:
        """Retain the network and dynamic header collaborators without exposing values.

        Args:
            network (McpNetworkSettings): Optional proxy setting for the HTTP client.
            resolver (Any): Renders headers and obtains OBO tokens per JSON-RPC request.
        """
        self._network = network
        self._resolver = resolver

    async def _apply_request_headers(self, request: Any) -> None:
        """Apply correlated request headers or session-bound HTTP headers.

        Args:
            request (Any): HTTPX request prepared by the Streamable HTTP transport.
        """
        if request.method not in {"GET", "POST", "DELETE"}:
            return
        request_id: str | int | None = None
        if request.method == "POST":
            try:
                payload = json.loads(request.content)
            except (UnicodeDecodeError, ValueError):
                return
            if not isinstance(payload, dict):
                return
            candidate = payload.get("id")
            if isinstance(candidate, (str, int)):
                request_id = candidate
        headers = (
            await self._resolver.for_request(request_id)
            if request_id is not None
            else await self._resolver.for_session()
        )
        for name, value in headers.items():
            if name.casefold() not in self._TRANSPORT_HEADERS:
                request.headers[name] = value

    def __call__(
        self,
        headers: dict[str, str] | None = None,
        timeout: Any = None,
        auth: Any = None,
    ) -> Any:
        """Create an HTTPX client while preserving SDK timeouts and OAuth auth.

        Args:
            headers (dict[str, str] | None): Configured headers shared by the connection.
            timeout (Any): HTTPX timeout selected by the MCP transport.
            auth (Any): Existing OAuth handler, when the client performs interactive OAuth.
        """
        if httpx is None:
            raise RuntimeError("the 'mcp' extra is required for HTTP MCP connections")
        options: dict[str, Any] = {
            "headers": headers,
            "timeout": timeout,
            "auth": auth,
            "event_hooks": {"request": [self._apply_request_headers]},
        }
        if self._network.proxy_url is not None:
            options["proxy"] = self._network.proxy_url
        return httpx.AsyncClient(**options)

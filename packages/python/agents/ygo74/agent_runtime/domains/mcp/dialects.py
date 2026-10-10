"""Choosing which client speaks to a bound server.

A dialect is the translation between one server's shapes and an application's
domain. It exists because most servers were not written for that application: one
has its own tool names and payloads, and the next will have others again. Rather
than teach every capability about each of them, one class per server implements
the application's tool port, and the capabilities never find out which one they
are talking to.

Only the *mechanics* live here. Which dialects exist, and what they translate to,
is the application's business - this registry holds no knowledge of any of them.

Registration is explicit rather than discovered: which servers a deployment can
reach is a decision worth reading in one place, and a typo in a binding file
should name the alternatives rather than fail deep inside a session.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any, Concatenate, Generic, ParamSpec, TypeVar

from ygo74.agent_runtime.domains.mcp.binding import McpServerBinding
from ygo74.agent_runtime.domains.mcp.mcp_errors import McpToolUnavailableError

ToolsT = TypeVar("ToolsT")
P = ParamSpec("P")
ErrorFactory = Callable[[str], Exception]

_logger = logging.getLogger(__name__)

DialectFactory = Callable[Concatenate[McpServerBinding[Any], P], ToolsT]


class DialectRegistry(Generic[ToolsT, P]):
    """The dialects this build knows how to speak.

    Args:
        dialects (Mapping[str, DialectFactory[P, ToolsT]] | None): Provider response dialects available for the configured endpoint.
        unavailable (ErrorFactory): Response or fallback used when the underlying service is unavailable.
    """
    def __init__(
        self,
        dialects: Mapping[str, DialectFactory[P, ToolsT]] | None = None,
        *,
        unavailable: ErrorFactory = McpToolUnavailableError,
    ) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            dialects (Mapping[str, DialectFactory[P, ToolsT]] | None): Provider response dialects available for the configured endpoint.
            unavailable (ErrorFactory): Response or fallback used when the underlying service is unavailable.
        """
        self._dialects: dict[str, DialectFactory[P, ToolsT]] = dict(dialects or {})
        self._unavailable = unavailable

    @property
    def known(self) -> tuple[str, ...]:
        """The names this registry answers to, in a stable order."""
        return tuple(sorted(self._dialects))

    def register(self, name: str, factory: DialectFactory[P, ToolsT]) -> None:
        """Add a dialect, refusing to silently replace one.

        Replacing quietly is how a deployment ends up talking to a server it did
        not mean to, with nothing in the logs to say when it changed.

        Args:
            name (str): The name used to locate or label the value.
            factory (DialectFactory[P, ToolsT]): Factory that creates or retrieves the requested runtime component.
        """
        if name in self._dialects:
            raise self._unavailable(f"dialect {name!r} is already registered")
        self._dialects[name] = factory

    def build(self, binding: McpServerBinding[Any], *args: P.args, **kwargs: P.kwargs) -> ToolsT:
        """Build the client a binding asks for.

        The extra arguments are handed to the factory untouched: what a dialect
        needs to be constructed - a connection, an owner, a credential - is its
        own business.

        Args:
            binding (McpServerBinding[Any]): MCP transport binding and its authentication metadata.
            args (P.args): Positional arguments forwarded to the wrapped function.
            kwargs (P.kwargs): Keyword arguments forwarded to the wrapped function.
        """
        factory = self._dialects.get(binding.dialect)
        if factory is None:
            raise self._unavailable(
                f"server {binding.server!r} speaks the {binding.dialect!r} dialect, which is not implemented. "
                f"Known dialects: {', '.join(self.known)}."
            )
        _logger.debug("building dialect %r for server %r", binding.dialect, binding.server)
        return factory(binding, *args, **kwargs)

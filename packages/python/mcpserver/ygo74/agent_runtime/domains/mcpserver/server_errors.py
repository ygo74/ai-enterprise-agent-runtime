"""Failures that stop an MCP server from being served at all.

Both of these are deliberately fatal, and both exist because the alternative is a
server that runs and looks healthy while doing the wrong thing. A process that
refuses to start is a cheap, loud failure somebody fixes in a minute; a process
serving its tools to an unauthenticated network, or answering every real request
with 421 behind a green health probe, is neither cheap nor loud.
"""

from __future__ import annotations


class McpServerError(RuntimeError):
    """Base of the failures raised while standing an MCP server up."""


class McpServerConfigurationError(McpServerError):
    """Raised when the server cannot be served safely as configured."""


class McpServerUnreachableError(McpServerError):
    """Raised when the server would refuse the callers it was deployed for.

    Found the hard way: ``FastMCP`` derives its DNS-rebinding allow-list from the
    bind address at construction and never revisits it, so a server built with the
    default address answers every request carrying a service name in ``Host`` with
    421 - after authentication, before any tool, with the health probe still green.
    """

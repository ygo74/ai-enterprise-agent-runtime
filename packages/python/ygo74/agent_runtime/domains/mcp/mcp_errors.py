"""Errors of the Model Context Protocol boundary.

Three failures, and the distinction between them is what a caller acts on: a
server that cannot be reached, a binding that cannot be used as declared, and a
payload that does not match the contract.
"""

from __future__ import annotations


class McpError(Exception):
    """Base class for every failure at the tool boundary."""


class McpToolUnavailableError(McpError):
    """Raised when a server could not be reached, or refused the call.

    Transport failures are translated into this at the boundary. Nothing above
    ever sees an anyio cancellation, an HTTP status or a broken pipe: it sees a
    tool that could not be reached.
    """


class McpBindingError(McpError):
    """Raised when a delivered binding cannot be used as declared."""

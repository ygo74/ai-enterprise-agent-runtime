"""Errors raised when a request does not satisfy an agent contract.

Separate from the authentication and authorization errors: nothing here says a
caller was refused, only that what arrived cannot be answered as written.
"""

from __future__ import annotations


class AgentContractError(Exception):
    """Base class for a request that violates an agent contract."""


class EmptyRequestError(AgentContractError):
    """Raised when a request carries nothing for the agent to answer.

    Reported rather than answered with silence: an agent replying to an empty
    message would look like a model failure instead of a malformed request.
    """

    def __init__(self) -> None:
        super().__init__("the request carried no user message")

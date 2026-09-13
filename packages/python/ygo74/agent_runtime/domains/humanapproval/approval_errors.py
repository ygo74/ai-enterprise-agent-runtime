"""The vocabulary of a human approval that was required, refused or mismatched.

These are the three ways a gated operation can fail to proceed, and each says
something different to whoever reads it. They derive from
:class:`ygo74.agent_runtime.domains.security.security_errors.SecurityError`, so a
host can still catch the whole security model with one ``except`` while keeping
the distinctions where it needs them.
"""

from __future__ import annotations

from ygo74.agent_runtime.domains.security.security_errors import SecurityError


class ConfirmationRequiredError(SecurityError):
    """Raised when a gated operation is attempted without an approval decision."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(f"operation {tool_name!r} requires an explicit user confirmation")
        self.tool_name = tool_name


class ConfirmationRejectedError(SecurityError):
    """Raised when the user explicitly declined a gated operation."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(f"operation {tool_name!r} was declined by the user")
        self.tool_name = tool_name


class ConfirmationMismatchError(SecurityError):
    """Raised when an approval decision does not match the pending request.

    This blocks replaying a confirmation obtained for another operation.
    """

    def __init__(self, expected_request_id: str, received_request_id: str) -> None:
        super().__init__(f"confirmation {received_request_id!r} does not match pending request {expected_request_id!r}")
        self.expected_request_id = expected_request_id
        self.received_request_id = received_request_id

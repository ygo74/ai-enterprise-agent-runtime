"""Errors of the security model.

These are domain errors: they carry meaning about a decision the application
made, not about a transport. They are deliberately separate from
:mod:`ygo74.agent_runtime.domains.auth.auth_errors`, whose ``AuthenticationError``
and ``AuthorizationError`` describe what an HTTP surface does with a request the
runtime itself rejected.

The distinction matters at the call site. ``AuthorizationError`` is raised by a
handler to deny a request the runtime already authenticated, and the runtime maps
it to a 403. :class:`PermissionDeniedError` is raised inside a capability when the
caller does not hold the permission the operation declares, and what the
application does with it is the application's decision.
"""

from __future__ import annotations


class SecurityError(Exception):
    """Base class for every failure of the security model."""


class PermissionDeniedError(SecurityError):
    """Raised when a user context lacks the permission an operation requires.

    Args:
        user_id (str): Stable identifier of the authenticated user.
        required_permission (str): Permission the caller must have to run the operation.
    """
    def __init__(self, user_id: str, required_permission: str) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            user_id (str): Stable identifier of the authenticated user.
            required_permission (str): Permission the caller must have to run the operation.
        """
        super().__init__(f"user {user_id!r} is not allowed to perform {required_permission!r}")
        self.user_id = user_id
        self.required_permission = required_permission

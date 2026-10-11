"""Build the operation context from an authenticated caller and app policy."""

from __future__ import annotations

from collections.abc import Iterable

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.user_context import UserContext


class UserContextFactory:
    """Turn an authenticated principal into the context carried by operations."""
    def for_principal(
        self,
        principal: AgentPrincipal,
        *,
        session_id: str,
        permissions: Iterable[Permission],
    ) -> UserContext:
        """Return a context without deriving permissions from principal claims.

        Args:
            principal (AgentPrincipal): Authenticated principal whose identity and claims are being projected.
            session_id (str): Stable authenticated session identifier.
            permissions (Iterable[Permission]): Permissions granted to the user or required by the operation.
        """
        return UserContext(
            user_id=principal.subject,
            session_id=session_id,
            permissions=frozenset(permissions),
        )

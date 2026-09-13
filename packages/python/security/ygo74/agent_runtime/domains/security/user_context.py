"""Identity carried by every operation that touches protected information."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.security_errors import PermissionDeniedError


class UserContext(BaseModel):
    """Who is asking, for the duration of one conversation.

    This object is allowed to reach prompts and logs, therefore it must never
    hold a credential, an OAuth token or a password. Authentication material
    stays in the infrastructure layer, behind the tool boundary.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    permissions: frozenset[Permission] = frozenset()

    def has_permission(self, permission: Permission) -> bool:
        """Whether the caller holds the given permission."""
        return permission in self.permissions

    def require_permission(self, permission: Permission) -> None:
        """Fail fast when the caller lacks the given permission."""
        if permission in self.permissions:
            return
        raise PermissionDeniedError(self.user_id, permission.value)

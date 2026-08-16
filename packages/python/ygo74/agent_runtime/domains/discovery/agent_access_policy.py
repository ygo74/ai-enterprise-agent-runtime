"""Developer-supplied authorization policy shared by discovery and invocation.

Authorization decisions still belong to the developer -- the runtime never
invents a rule on its own -- but a single :class:`AgentAccessPolicy` is now the
one place that decision lives, instead of being duplicated inside every
entrypoint. The runtime calls ``is_authorized`` at two points with the same
descriptor and the same authenticated context:

- Before dispatching an invocation (``/v1/responses``, ``/v1/chat/completions``,
  ``/v1/messages``): a denial raises :class:`AuthorizationError`, mapped to
  HTTP 403.
- While serving discovery (``GET /v1/models`` and ``GET /v1/models/{id}``): a
  denied agent is filtered out of listings and its direct retrieval reports
  404, exactly like a hidden agent, so a caller never sees an entry it would
  immediately be denied for.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ygo74.agent_runtime.domains.auth.auth_context import AuthenticatedUserContext
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor


@runtime_checkable
class AgentAccessPolicy(Protocol):
    """Contract for the single authorization rule reused across every agent-scoped route."""

    def is_authorized(
        self,
        descriptor: AgentDescriptor,
        auth_context: AuthenticatedUserContext | None,
    ) -> bool:
        """Return ``True`` when ``auth_context`` may see and invoke ``descriptor``."""
        ...


@dataclass(slots=True)
class RoleRequiredAccessPolicy:
    """Ready-made policy denying callers who lack a single required role.

    Applies uniformly to every descriptor. Leave ``required_role`` empty to
    allow any caller, including anonymous ones.
    """

    required_role: str = ""

    def is_authorized(
        self,
        descriptor: AgentDescriptor,
        auth_context: AuthenticatedUserContext | None,
    ) -> bool:
        if not self.required_role:
            return True
        if auth_context is None:
            return False
        return auth_context.has_role(self.required_role)

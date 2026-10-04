"""Permissions a caller may hold.

A permission is declared by the domain that owns it - mail, Jira, Confluence -
and never by a central list in this library. That keeps a new agent from forcing
a change here, and keeps two domains from knowing about each other.

Permissions stay coarse: fine-grained authorisation belongs to the source system,
which remains the authority. These values only gate what an application is
willing to attempt on the caller's behalf.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ygo74.agent_runtime.domains.security.security_errors import SecurityError

_SEPARATOR = ":"


class UnknownPermissionError(SecurityError):
    """Raised when a configured permission was declared by no domain.

    Configuration names permissions as text. Resolving that text against the
    declared permissions is what keeps a typo from silently granting nothing -
    or from being read as a permission that does not exist.

    Args:
        value (str): The value being converted, checked, or serialized.
    """
    def __init__(self, value: str) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            value (str): The value being converted, checked, or serialized.
        """
        super().__init__(f"permission {value!r} is not declared by any domain")
        self.value = value


@dataclass(frozen=True, slots=True, order=True)
class Permission:
    """One capability, namespaced by the domain that declares it.

    Args:
        domain (str): Permission or origin domain used in its serialized identity.
        action (str): Permission action being evaluated.
    """
    domain: str
    action: str

    def __post_init__(self) -> None:
        """Reject a permission that could not be written as ``domain:action``."""
        # Check both permission components so the serialized domain:action key remains unambiguous and nonempty.
        for part in (self.domain, self.action):
            if not part or _SEPARATOR in part:
                raise ValueError(f"invalid permission part {part!r}")

    @property
    def value(self) -> str:
        """Canonical text form, as used in configuration and audit records."""
        return f"{self.domain}{_SEPARATOR}{self.action}"

    def __str__(self) -> str:
        """Return the canonical text form."""
        return self.value


class PermissionRegistry:
    """Resolves the permissions declared by the domains in use.

    The registry is built explicitly from the declarations of the domains an
    application composes, rather than populated by imports. Nothing is registered
    as a side effect, so a test builds exactly the registry it means to test.

    Args:
        permissions (Iterable[Permission]): Permissions granted to the user or required by the operation.
    """
    def __init__(self, permissions: Iterable[Permission]) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            permissions (Iterable[Permission]): Permissions granted to the user or required by the operation.
        """
        self._by_value = {permission.value: permission for permission in permissions}

    def resolve(self, value: str) -> Permission:
        """Return the declared permission carrying the given text form.

        Args:
            value (str): The value being converted, checked, or serialized.
        """
        permission = self._by_value.get(value)
        if permission is None:
            raise UnknownPermissionError(value)
        return permission

    def declared(self) -> frozenset[Permission]:
        """Return every permission the registry knows about."""
        return frozenset(self._by_value.values())

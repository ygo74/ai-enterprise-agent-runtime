"""Structured discovery errors mapped onto the shared error envelope."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope


class DiscoveryErrorCategory(StrEnum):
    """Envelope categories used by the discovery surfaces."""
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"


class DiscoveryErrorCode(StrEnum):
    """Stable, cross-language discovery error codes."""
    DUPLICATE_AGENT_ID = "duplicate_agent_id"
    UNRESOLVED_ROUTE_KEY = "unresolved_route_key"
    CAPABILITY_CONTRADICTION = "capability_contradiction"
    INVALID_DESCRIPTOR = "invalid_descriptor"
    AGENT_NOT_FOUND = "agent_not_found"
    SURFACE_DISABLED = "discovery_surface_disabled"
    UNSUPPORTED_PROVIDER_VERSION = "unsupported_provider_version"
    INVALID_PAGINATION = "invalid_pagination"


@dataclass(slots=True)
class DiscoveryError(Exception):
    """Raised by the discovery domain for every structured failure.

    Args:
        code (DiscoveryErrorCode): Stable error or diagnostic code returned to the caller.
        message (str): Framework message or protocol message being converted.
        category (DiscoveryErrorCategory): Content or error category used to select the applicable mapping.
        details (Any | None): Framework-provided token counters to validate and aggregate.
    """
    code: DiscoveryErrorCode
    message: str
    category: DiscoveryErrorCategory = DiscoveryErrorCategory.VALIDATION
    details: Any | None = None

    def to_envelope(self) -> ErrorEnvelope:
        """Convert a discovery error into the shared structured error envelope.
        """
        return ErrorEnvelope(
            code=str(self.code),
            category=str(self.category),
            message=self.message,
            details=self.details,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the instance runtime data into its documented dictionary representation.
        """
        payload: dict[str, Any] = {
            "code": str(self.code),
            "category": str(self.category),
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


class DiscoveryErrors:
    """Factory for the discovery failures the runtime is allowed to raise.

    Retrieval denials and unknown identifiers deliberately share
    :meth:`agent_not_found` so a caller cannot distinguish a hidden agent from a
    non-existent one.
    """
    @staticmethod
    def duplicate_agent_id(agent_id: str) -> DiscoveryError:
        """Create an error identifying an agent ID already registered by another descriptor.

        Args:
            agent_id (str): Public identifier of the agent being registered or discovered.
        """
        return DiscoveryError(
            code=DiscoveryErrorCode.DUPLICATE_AGENT_ID,
            category=DiscoveryErrorCategory.CONFIGURATION,
            message=f"Duplicate agent identifier '{agent_id}'. Each exposed agent needs a unique agentId.",
            details={"agentId": agent_id},
        )

    @staticmethod
    def unresolved_route_key(agent_id: str, route_key: str) -> DiscoveryError:
        """Create an error when a descriptor references a route that is not registered.

        Args:
            agent_id (str): Public identifier of the agent being registered or discovered.
            route_key (str): The registered route key that identifies the target agent or handler.
        """
        return DiscoveryError(
            code=DiscoveryErrorCode.UNRESOLVED_ROUTE_KEY,
            category=DiscoveryErrorCategory.CONFIGURATION,
            message=(
                f"Agent '{agent_id}' is bound to route key '{route_key}', "
                "which has no registered handler."
            ),
            details={"agentId": agent_id, "routeKey": route_key},
        )

    @staticmethod
    def capability_contradiction(agent_id: str, capability: str, reason: str) -> DiscoveryError:
        """Create an error when declared capabilities conflict with enabled endpoints.

        Args:
            agent_id (str): Public identifier of the agent being registered or discovered.
            capability (str): Capability declaration checked against the runtime configuration.
            reason (str): Reason code or message associated with this decision or failure.
        """
        return DiscoveryError(
            code=DiscoveryErrorCode.CAPABILITY_CONTRADICTION,
            category=DiscoveryErrorCategory.CONFIGURATION,
            message=f"Agent '{agent_id}' declares capability '{capability}' but {reason}.",
            details={"agentId": agent_id, "capability": capability},
        )

    @staticmethod
    def invalid_descriptor(field: str, reason: str) -> DiscoveryError:
        """Create a validation error tied to the descriptor field that failed.

        Args:
            field (str): Descriptor field associated with a validation failure.
            reason (str): Reason code or message associated with this decision or failure.
        """
        return DiscoveryError(
            code=DiscoveryErrorCode.INVALID_DESCRIPTOR,
            category=DiscoveryErrorCategory.VALIDATION,
            message=f"Invalid agent descriptor: {field} {reason}.",
            details={"field": field},
        )

    @staticmethod
    def agent_not_found(agent_id: str) -> DiscoveryError:
        """Create the provider-compatible not-found error for an unknown agent identifier.

        Args:
            agent_id (str): Public identifier of the agent being registered or discovered.
        """
        return DiscoveryError(
            code=DiscoveryErrorCode.AGENT_NOT_FOUND,
            category=DiscoveryErrorCategory.NOT_FOUND,
            message=f"No agent matches identifier '{agent_id}'.",
            details={"agentId": agent_id},
        )

    @staticmethod
    def surface_disabled(surface: str) -> DiscoveryError:
        """Create an error for a discovery surface disabled by configuration.

        Args:
            surface (str): Endpoint or discovery surface whose configuration is being checked.
        """
        return DiscoveryError(
            code=DiscoveryErrorCode.SURFACE_DISABLED,
            category=DiscoveryErrorCategory.NOT_FOUND,
            message=f"Discovery surface '{surface}' is not enabled.",
            details={"surface": surface},
        )

    @staticmethod
    def unsupported_provider_version(version: str) -> DiscoveryError:
        """Create an error for an unsupported provider protocol version.

        Args:
            version (str): Agent or API version reported through discovery.
        """
        return DiscoveryError(
            code=DiscoveryErrorCode.UNSUPPORTED_PROVIDER_VERSION,
            category=DiscoveryErrorCategory.VALIDATION,
            message=f"Unsupported provider protocol version '{version}'.",
            details={"version": version},
        )

    @staticmethod
    def invalid_pagination(reason: str) -> DiscoveryError:
        """Create a validation error for malformed or inconsistent pagination parameters.

        Args:
            reason (str): Reason code or message associated with this decision or failure.
        """
        return DiscoveryError(
            code=DiscoveryErrorCode.INVALID_PAGINATION,
            category=DiscoveryErrorCategory.VALIDATION,
            message=f"Invalid pagination parameters: {reason}.",
            details={"reason": reason},
        )

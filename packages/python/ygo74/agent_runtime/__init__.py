"""Public surface of the agent runtime.

Every name below is resolved on first use rather than on import. That is not a
micro-optimisation: this package spans domains with very different dependencies,
and one of them - ``domains.endpoints`` - imports FastAPI.

Eager re-exports made that unavoidable. Importing the permission model, the
security floor or an agent contract executed this module, which loaded the
endpoint adapters, which imported a web framework into a process that had no use
for one. The ``http`` extra was then optional only in the sense that its absence
did not crash: the code was loaded either way, and a domain test could not prove
it ran without a web stack.

Resolution is per name, through :pep:`562`. ``from ygo74.agent_runtime import
AgentPrincipal`` imports one module; ``import
ygo74.agent_runtime.domains.security.permissions`` imports none of the others.
``dir()`` and ``__all__`` still list the whole surface, and type checkers read the
``TYPE_CHECKING`` block below, so nothing about the public API changes.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

_EXPORTS: dict[str, str] = {
    "StandardExchangeRequest":   "domains.contracts.exchange_models",
    "StandardExchangeResponse":  "domains.contracts.exchange_models",
    "ErrorEnvelope":             "domains.contracts.error_envelope",
    "AgentContractError":        "domains.contracts.contract_errors",
    "EmptyRequestError":         "domains.contracts.contract_errors",
    "AgentReply":                "domains.contracts.conversation",
    "ConversationEngine":        "domains.contracts.conversation",
    "ConversationTurn":          "domains.contracts.conversation",
    "AgentManifest":             "domains.contracts.manifests",
    "SkillManifest":             "domains.contracts.manifests",
    "ResultRenderer":            "domains.contracts.capability_registry",
    "SkillDescriptor":           "domains.contracts.capability_registry",
    "SkillInvocation":           "domains.contracts.capability_registry",
    "SkillRegistry":             "domains.contracts.capability_registry",
    "AuthenticatedUserContext":  "domains.auth.auth_context",
    "ResolvedUser":              "domains.auth.auth_context",
    "UserIdentity":              "domains.auth.auth_context",
    "AuthenticationError":       "domains.auth.auth_errors",
    "AuthorizationError":        "domains.auth.auth_errors",
    "AgentPrincipal":            "domains.auth.agent_principal",
    "PrincipalError":            "domains.auth.agent_principal",
    "Authenticator":             "domains.auth.authenticator",
    "RequestAuthenticator":      "domains.auth.authenticator",
    "ApiKeyAuthenticator":       "domains.auth.apikey_authenticator",
    "ApiKeyUserResolver":        "domains.auth.apikey_authenticator",
    "StaticApiKeyUserResolver":  "domains.auth.apikey_authenticator",
    "JwtAuthenticator":          "domains.auth.jwt_authenticator",
    "JwtValidationConfig":       "domains.auth.jwt_authenticator",
    "AgentCapabilitySet":        "domains.discovery.agent_descriptor",
    "AgentDescriptor":           "domains.discovery.agent_descriptor",
    "AgentSkill":                "domains.discovery.agent_descriptor",
    "CapabilitySizeUnit":        "domains.discovery.agent_descriptor",
    "DiscoveryVisibility":       "domains.discovery.agent_descriptor",
    "Modality":                  "domains.discovery.agent_descriptor",
    "AgentAccessPolicy":         "domains.discovery.agent_access_policy",
    "RoleRequiredAccessPolicy":  "domains.discovery.agent_access_policy",
    "AnthropicModelProjection":  "domains.discovery.anthropic_model_projection",
    "CapabilityExtensions":      "domains.discovery.capability_extensions",
    "CapabilityValidator":       "domains.discovery.capability_validator",
    "DescriptorBinding":         "domains.discovery.descriptor_binding",
    "DescriptorDefaults":        "domains.discovery.descriptor_defaults",
    "DescriptorOrdering":        "domains.discovery.descriptor_registry",
    "DescriptorRegistry":        "domains.discovery.descriptor_registry",
    "DialectSelection":          "domains.discovery.dialect_selector",
    "DialectSelector":           "domains.discovery.dialect_selector",
    "ProviderDialect":           "domains.discovery.dialect_selector",
    "DiscoveryConfiguration":    "domains.discovery.discovery_configuration",
    "DiscoveryService":          "domains.discovery.discovery_configuration",
    "DiscoverySurface":          "domains.discovery.discovery_configuration",
    "DiscoveryError":            "domains.discovery.discovery_errors",
    "DiscoveryErrorCategory":    "domains.discovery.discovery_errors",
    "DiscoveryErrorCode":        "domains.discovery.discovery_errors",
    "DiscoveryErrors":           "domains.discovery.discovery_errors",
    "ModelRouteResolver":        "domains.discovery.model_route_resolver",
    "OpenAiModelProjection":     "domains.discovery.openai_model_projection",
    "DiscoveryPagination":       "domains.discovery.pagination",
    "PaginationRequest":         "domains.discovery.pagination",
    "PaginationResult":          "domains.discovery.pagination",
    "add_ai_endpoint":           "domains.endpoints.fastapi_endpoints",
    "add_ai_endpoints":          "domains.endpoints.fastapi_endpoints",
    "add_discovery_endpoints":   "domains.endpoints.fastapi_endpoints",
    "CREDENTIAL_HEADERS":        "domains.endpoints.header_forwarding",
    "DEFAULT_CONVERSATION_HEADER": "domains.endpoints.header_forwarding",
    "DEFAULT_FORWARDED_HEADERS": "domains.endpoints.header_forwarding",
    "RequestHeaderForwarder":    "domains.endpoints.header_forwarding",
    "DEFAULT_CONVERSATION":      "domains.endpoints.conversation_payloads",
    "AgentReplyRenderer":        "domains.endpoints.conversation_payloads",
    "ConversationPayloadReader": "domains.endpoints.conversation_payloads",
    "latest_message":            "domains.endpoints.conversation_payloads",
    "PermissionDeniedError":     "domains.security.security_errors",
    "SecurityError":             "domains.security.security_errors",
    "Permission":                "domains.security.permissions",
    "PermissionRegistry":        "domains.security.permissions",
    "UnknownPermissionError":    "domains.security.permissions",
    "UserContext":               "domains.security.user_context",
    "OperationType":             "domains.security.operations",
    "RiskLevel":                 "domains.security.operations",
    "ToolOperationDescriptor":   "domains.security.operations",
    "OperationFloor":            "domains.security.floor",
    "SecurityFloor":             "domains.security.floor",
    "SecurityFloorViolationError": "domains.security.floor",
    "AuditOutcome":              "domains.security.audit",
    "AuditRecord":               "domains.security.audit",
    "AuditTrail":                "domains.security.audit",
    "InMemoryAuditTrail":        "domains.security.audit",
    "LoggingAuditTrail":         "domains.security.audit",
    "AccessToken":               "domains.auth.tokens",
    "TokenError":                "domains.auth.tokens",
    "TokenVerificationError":    "domains.auth.tokens",
    "TokenExchangeError":        "domains.auth.tokens",
    "TokenVerifier":             "domains.auth.tokens",
    "DelegatedTokenSource":      "domains.auth.tokens",
    "AdvertisedSecurity":        "domains.discovery.manifest_descriptor",
    "AgentDescriptorFactory":    "domains.discovery.manifest_descriptor",
    "SecurityScheme":            "domains.discovery.manifest_descriptor",
    "ConfirmationRequiredError":           "domains.humanapproval.approval_errors",
    "ConfirmationRejectedError":           "domains.humanapproval.approval_errors",
    "ConfirmationMismatchError":           "domains.humanapproval.approval_errors",
    "ConfirmationPreferences":             "domains.humanapproval.confirmation",
    "ConfirmationPreferenceStore":         "domains.humanapproval.confirmation",
    "InMemoryConfirmationPreferenceStore": "domains.humanapproval.confirmation",
    "ConfirmationPolicy":                  "domains.humanapproval.confirmation",
    "ConfiguredConfirmationPolicy":        "domains.humanapproval.confirmation",
    "ConfirmationDetail":                  "domains.humanapproval.confirmation",
    "ConfirmationKey":                     "domains.humanapproval.confirmation",
    "ConfirmationRequest":                 "domains.humanapproval.confirmation",
    "ConfirmationDecision":                "domains.humanapproval.confirmation",
    "ConfirmationOutcome":                 "domains.humanapproval.confirmation",
    "ConfirmationAuthority":               "domains.humanapproval.confirmation",
    "ConfirmationLedger":                  "domains.humanapproval.confirmation",
    "ConfirmationGate":                    "domains.humanapproval.confirmation",
    "InMemoryConfirmationLedger":          "domains.humanapproval.ledger",
    "ConfirmationBroker":                  "domains.humanapproval.broker",
    "UnattendedApprovalAuthority":         "domains.humanapproval.unattended",
    "ConfirmationTicket":                  "domains.humanapproval.tickets",
    "PendingConfirmationStore":            "domains.humanapproval.tickets",
    "InMemoryPendingConfirmationStore":    "domains.humanapproval.tickets",
    "TicketError":                         "domains.humanapproval.tickets",
    "UnknownTicketError":                  "domains.humanapproval.tickets",
    "new_ticket_id":                       "domains.humanapproval.tickets",
    "TICKET_PREFIX":                       "domains.humanapproval.tickets",
    "ConfirmationVerb":                    "domains.humanapproval.commands",
    "ConfirmationCommand":                 "domains.humanapproval.commands",
    "ConfirmationCommandParser":           "domains.humanapproval.commands",
    "ConfirmationPresenter":               "domains.humanapproval.confirmed_operations",
    "ConfirmedOperationRunner":            "domains.humanapproval.confirmed_operations",
    "PendingConfirmationRenderer":         "domains.humanapproval.pending_renderer",
    "OperationCatalogue":                  "domains.humanapproval.gated_operations",
    "GatedOperationRunner":                "domains.humanapproval.gated_operations",
    "UntrustedOrigin":                 "domains.security.untrusted",
    "UntrustedText":                   "domains.security.untrusted",
    "untrusted":                       "domains.security.untrusted",
    "UntrustedFence":                  "domains.security.fencing",
    "untrusted_contract":              "domains.security.fencing",
    "UNTRUSTED_CONTRACT":              "domains.security.fencing",
    "DEFAULT_UNTRUSTED_SOURCE":        "domains.security.fencing",
    "UntrustedSection":                "domains.security.prompt_envelope",
    "ReasoningRequest":                "domains.security.prompt_envelope",
    "PromptEnvelopeBuilder":           "domains.security.prompt_envelope",
    "ConversationRuntimeCache":        "domains.sessions.conversation_cache",
    "OidcDiscovery":                   "domains.auth.oidc_discovery",
    "AgentHttpSettings":               "domains.configuration.agent_http_settings",
    "McpError":                        "domains.mcp.mcp_errors",
    "McpBindingError":                 "domains.mcp.mcp_errors",
    "McpToolUnavailableError":         "domains.mcp.mcp_errors",
    "McpTransport":                    "domains.mcp.binding",
    "McpServerBinding":                "domains.mcp.binding",
    "McpServerBindingLoader":          "domains.mcp.binding",
    "McpConnection":                   "domains.mcp.binding",
    "DialectRegistry":                 "domains.mcp.dialects",
    "LoopbackConsent":                 "domains.mcp.oauth",
    "FileTokenStorage":                "domains.mcp.oauth",
    "PinnedScopeOAuthProvider":        "domains.mcp.oauth",
    "loopback_redirect_uri":           "domains.mcp.oauth",
}

__all__ = [
    "AccessToken",
    "AdvertisedSecurity",
    "AgentAccessPolicy",
    "AgentCapabilitySet",
    "AgentContractError",
    "AgentDescriptor",
    "AgentDescriptorFactory",
    "AgentHttpSettings",
    "AgentManifest",
    "AgentPrincipal",
    "AgentReply",
    "AgentReplyRenderer",
    "AgentSkill",
    "AnthropicModelProjection",
    "ApiKeyAuthenticator",
    "ApiKeyUserResolver",
    "AuditOutcome",
    "AuditRecord",
    "AuditTrail",
    "AuthenticatedUserContext",
    "AuthenticationError",
    "Authenticator",
    "AuthorizationError",
    "CREDENTIAL_HEADERS",
    "CapabilityExtensions",
    "CapabilitySizeUnit",
    "CapabilityValidator",
    "ConfiguredConfirmationPolicy",
    "ConfirmationAuthority",
    "ConfirmationBroker",
    "ConfirmationCommand",
    "ConfirmationCommandParser",
    "ConfirmationDecision",
    "ConfirmationDetail",
    "ConfirmationGate",
    "ConfirmationKey",
    "ConfirmationLedger",
    "ConfirmationMismatchError",
    "ConfirmationOutcome",
    "ConfirmationPolicy",
    "ConfirmationPreferenceStore",
    "ConfirmationPreferences",
    "ConfirmationPresenter",
    "ConfirmationRejectedError",
    "ConfirmationRequest",
    "ConfirmationRequiredError",
    "ConfirmationTicket",
    "ConfirmationVerb",
    "ConfirmedOperationRunner",
    "ConversationEngine",
    "ConversationPayloadReader",
    "ConversationRuntimeCache",
    "ConversationTurn",
    "DEFAULT_CONVERSATION",
    "DEFAULT_CONVERSATION_HEADER",
    "DEFAULT_FORWARDED_HEADERS",
    "DEFAULT_UNTRUSTED_SOURCE",
    "DelegatedTokenSource",
    "DescriptorBinding",
    "DescriptorDefaults",
    "DescriptorOrdering",
    "DescriptorRegistry",
    "DialectRegistry",
    "DialectSelection",
    "DialectSelector",
    "DiscoveryConfiguration",
    "DiscoveryError",
    "DiscoveryErrorCategory",
    "DiscoveryErrorCode",
    "DiscoveryErrors",
    "DiscoveryPagination",
    "DiscoveryService",
    "DiscoverySurface",
    "DiscoveryVisibility",
    "EmptyRequestError",
    "ErrorEnvelope",
    "FileTokenStorage",
    "GatedOperationRunner",
    "InMemoryAuditTrail",
    "InMemoryConfirmationLedger",
    "InMemoryConfirmationPreferenceStore",
    "InMemoryPendingConfirmationStore",
    "JwtAuthenticator",
    "JwtValidationConfig",
    "LoggingAuditTrail",
    "LoopbackConsent",
    "McpBindingError",
    "McpConnection",
    "McpError",
    "McpServerBinding",
    "McpServerBindingLoader",
    "McpToolUnavailableError",
    "McpTransport",
    "Modality",
    "ModelRouteResolver",
    "OidcDiscovery",
    "OpenAiModelProjection",
    "OperationCatalogue",
    "OperationFloor",
    "OperationType",
    "PaginationRequest",
    "PaginationResult",
    "PendingConfirmationRenderer",
    "PendingConfirmationStore",
    "Permission",
    "PermissionDeniedError",
    "PermissionRegistry",
    "PinnedScopeOAuthProvider",
    "PrincipalError",
    "PromptEnvelopeBuilder",
    "ProviderDialect",
    "ReasoningRequest",
    "RequestAuthenticator",
    "RequestHeaderForwarder",
    "ResolvedUser",
    "ResultRenderer",
    "RiskLevel",
    "RoleRequiredAccessPolicy",
    "SecurityError",
    "SecurityFloor",
    "SecurityFloorViolationError",
    "SecurityScheme",
    "SkillDescriptor",
    "SkillInvocation",
    "SkillManifest",
    "SkillRegistry",
    "StandardExchangeRequest",
    "StandardExchangeResponse",
    "StaticApiKeyUserResolver",
    "TICKET_PREFIX",
    "TicketError",
    "TokenError",
    "TokenExchangeError",
    "TokenVerificationError",
    "TokenVerifier",
    "ToolOperationDescriptor",
    "UNTRUSTED_CONTRACT",
    "UnattendedApprovalAuthority",
    "UnknownPermissionError",
    "UnknownTicketError",
    "UntrustedFence",
    "UntrustedOrigin",
    "UntrustedSection",
    "UntrustedText",
    "UserContext",
    "UserIdentity",
    "add_ai_endpoint",
    "add_ai_endpoints",
    "add_discovery_endpoints",
    "latest_message",
    "loopback_redirect_uri",
    "new_ticket_id",
    "untrusted",
    "untrusted_contract",
]


def __getattr__(name: str) -> Any:
    """Import the module owning a public name, the first time it is asked for."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List the public surface without importing any of it."""
    return __all__


if TYPE_CHECKING:  # pragma: no cover - re-exported for type checkers only
    from ygo74.agent_runtime.domains.auth.oidc_discovery import OidcDiscovery
    from ygo74.agent_runtime.domains.configuration.agent_http_settings import AgentHttpSettings
    from ygo74.agent_runtime.domains.mcp.binding import (
        McpConnection,
        McpServerBinding,
        McpServerBindingLoader,
        McpTransport,
    )
    from ygo74.agent_runtime.domains.mcp.dialects import DialectRegistry
    from ygo74.agent_runtime.domains.mcp.mcp_errors import (
        McpBindingError,
        McpError,
        McpToolUnavailableError,
    )
    from ygo74.agent_runtime.domains.mcp.oauth import (
        FileTokenStorage,
        LoopbackConsent,
        PinnedScopeOAuthProvider,
        loopback_redirect_uri,
    )
    from ygo74.agent_runtime.domains.security.fencing import (
        DEFAULT_UNTRUSTED_SOURCE,
        UNTRUSTED_CONTRACT,
        UntrustedFence,
        untrusted_contract,
    )
    from ygo74.agent_runtime.domains.security.prompt_envelope import (
        PromptEnvelopeBuilder,
        ReasoningRequest,
        UntrustedSection,
    )
    from ygo74.agent_runtime.domains.security.untrusted import (
        UntrustedOrigin,
        UntrustedText,
        untrusted,
    )
    from ygo74.agent_runtime.domains.sessions.conversation_cache import ConversationRuntimeCache
    from ygo74.agent_runtime.domains.humanapproval.approval_errors import (
        ConfirmationMismatchError,
        ConfirmationRejectedError,
        ConfirmationRequiredError,
    )
    from ygo74.agent_runtime.domains.humanapproval.broker import ConfirmationBroker
    from ygo74.agent_runtime.domains.humanapproval.commands import (
        ConfirmationCommand,
        ConfirmationCommandParser,
        ConfirmationVerb,
    )
    from ygo74.agent_runtime.domains.humanapproval.confirmation import (
        ConfirmationAuthority,
        ConfirmationDecision,
        ConfirmationDetail,
        ConfirmationGate,
        ConfirmationKey,
        ConfirmationLedger,
        ConfirmationOutcome,
        ConfirmationPolicy,
        ConfirmationPreferences,
        ConfirmationPreferenceStore,
        ConfirmationRequest,
        ConfiguredConfirmationPolicy,
        InMemoryConfirmationPreferenceStore,
    )
    from ygo74.agent_runtime.domains.humanapproval.confirmed_operations import (
        ConfirmationPresenter,
        ConfirmedOperationRunner,
    )
    from ygo74.agent_runtime.domains.humanapproval.gated_operations import (
        GatedOperationRunner,
        OperationCatalogue,
    )
    from ygo74.agent_runtime.domains.humanapproval.ledger import InMemoryConfirmationLedger
    from ygo74.agent_runtime.domains.humanapproval.pending_renderer import PendingConfirmationRenderer
    from ygo74.agent_runtime.domains.humanapproval.tickets import (
        TICKET_PREFIX,
        ConfirmationTicket,
        InMemoryPendingConfirmationStore,
        PendingConfirmationStore,
        TicketError,
        UnknownTicketError,
        new_ticket_id,
    )
    from ygo74.agent_runtime.domains.humanapproval.unattended import UnattendedApprovalAuthority
    from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal, PrincipalError
    from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
        ApiKeyAuthenticator,
        ApiKeyUserResolver,
        StaticApiKeyUserResolver,
    )
    from ygo74.agent_runtime.domains.auth.auth_context import (
        AuthenticatedUserContext,
        ResolvedUser,
        UserIdentity,
    )
    from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError, AuthorizationError
    from ygo74.agent_runtime.domains.auth.authenticator import Authenticator, RequestAuthenticator
    from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtAuthenticator, JwtValidationConfig
    from ygo74.agent_runtime.domains.auth.tokens import (
        AccessToken,
        DelegatedTokenSource,
        TokenError,
        TokenExchangeError,
        TokenVerificationError,
        TokenVerifier,
    )
    from ygo74.agent_runtime.domains.discovery.manifest_descriptor import (
        AdvertisedSecurity,
        AgentDescriptorFactory,
        SecurityScheme,
    )
    from ygo74.agent_runtime.domains.contracts.capability_registry import (
        ResultRenderer,
        SkillDescriptor,
        SkillInvocation,
        SkillRegistry,
    )
    from ygo74.agent_runtime.domains.contracts.contract_errors import AgentContractError, EmptyRequestError
    from ygo74.agent_runtime.domains.contracts.conversation import (
        AgentReply,
        ConversationEngine,
        ConversationTurn,
    )
    from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
    from ygo74.agent_runtime.domains.contracts.exchange_models import (
        StandardExchangeRequest,
        StandardExchangeResponse,
    )
    from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
    from ygo74.agent_runtime.domains.discovery.agent_access_policy import (
        AgentAccessPolicy,
        RoleRequiredAccessPolicy,
    )
    from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
        AgentCapabilitySet,
        AgentDescriptor,
        AgentSkill,
        CapabilitySizeUnit,
        DiscoveryVisibility,
        Modality,
    )
    from ygo74.agent_runtime.domains.discovery.anthropic_model_projection import AnthropicModelProjection
    from ygo74.agent_runtime.domains.discovery.capability_extensions import CapabilityExtensions
    from ygo74.agent_runtime.domains.discovery.capability_validator import CapabilityValidator
    from ygo74.agent_runtime.domains.discovery.descriptor_binding import DescriptorBinding
    from ygo74.agent_runtime.domains.discovery.descriptor_defaults import DescriptorDefaults
    from ygo74.agent_runtime.domains.discovery.descriptor_registry import (
        DescriptorOrdering,
        DescriptorRegistry,
    )
    from ygo74.agent_runtime.domains.discovery.dialect_selector import (
        DialectSelection,
        DialectSelector,
        ProviderDialect,
    )
    from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
        DiscoveryConfiguration,
        DiscoveryService,
        DiscoverySurface,
    )
    from ygo74.agent_runtime.domains.discovery.discovery_errors import (
        DiscoveryError,
        DiscoveryErrorCategory,
        DiscoveryErrorCode,
        DiscoveryErrors,
    )
    from ygo74.agent_runtime.domains.discovery.model_route_resolver import ModelRouteResolver
    from ygo74.agent_runtime.domains.discovery.openai_model_projection import OpenAiModelProjection
    from ygo74.agent_runtime.domains.discovery.pagination import (
        DiscoveryPagination,
        PaginationRequest,
        PaginationResult,
    )
    from ygo74.agent_runtime.domains.endpoints.conversation_payloads import (
        DEFAULT_CONVERSATION,
        AgentReplyRenderer,
        ConversationPayloadReader,
        latest_message,
    )
    from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import (
        add_ai_endpoint,
        add_ai_endpoints,
        add_discovery_endpoints,
    )
    from ygo74.agent_runtime.domains.endpoints.header_forwarding import (
        CREDENTIAL_HEADERS,
        DEFAULT_CONVERSATION_HEADER,
        DEFAULT_FORWARDED_HEADERS,
        RequestHeaderForwarder,
    )
    from ygo74.agent_runtime.domains.security.audit import (
        AuditOutcome,
        AuditRecord,
        AuditTrail,
        InMemoryAuditTrail,
        LoggingAuditTrail,
    )
    from ygo74.agent_runtime.domains.security.floor import (
        OperationFloor,
        SecurityFloor,
        SecurityFloorViolationError,
    )
    from ygo74.agent_runtime.domains.security.operations import (
        OperationType,
        RiskLevel,
        ToolOperationDescriptor,
    )
    from ygo74.agent_runtime.domains.security.permissions import (
        Permission,
        PermissionRegistry,
        UnknownPermissionError,
    )
    from ygo74.agent_runtime.domains.security.security_errors import PermissionDeniedError, SecurityError
    from ygo74.agent_runtime.domains.security.user_context import UserContext
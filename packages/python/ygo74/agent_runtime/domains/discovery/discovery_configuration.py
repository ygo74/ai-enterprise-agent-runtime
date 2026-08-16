"""Discovery surface configuration and the service that serves the surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.discovery.anthropic_model_projection import AnthropicModelProjection
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.dialect_selector import (
    DialectSelection,
    DialectSelector,
    ProviderDialect,
)
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors
from ygo74.agent_runtime.domains.discovery.openai_model_projection import OpenAiModelProjection
from ygo74.agent_runtime.domains.discovery.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    DiscoveryPagination,
    PaginationRequest,
)


class DiscoverySurface(StrEnum):
    """Independently enablable discovery surfaces."""

    OPENAI_MODELS = "openai_models"
    ANTHROPIC_MODELS = "anthropic_models"
    AGENT_CARD = "agent_card"


@dataclass(slots=True)
class DiscoveryConfiguration:
    """Settings controlling which discovery surfaces are exposed and how they behave.

    ``external_base_url`` is what the agent card advertises as its endpoint
    location, so values stay correct when the runtime runs behind a reverse proxy
    and cannot infer its public address from the request.
    """

    enable_openai_models: bool = False
    enable_anthropic_models: bool = False
    enable_agent_card: bool = False
    dialect_selection: DialectSelection = DialectSelection.HEADER
    require_authentication: bool = False
    default_page_size: int = DEFAULT_PAGE_SIZE
    max_page_size: int = MAX_PAGE_SIZE
    external_base_url: str | None = None
    route_prefix: str = ""

    def __post_init__(self) -> None:
        if self.default_page_size < 1 or self.max_page_size < 1:
            raise DiscoveryErrors.invalid_pagination("page sizes must be positive")
        if self.default_page_size > self.max_page_size:
            raise DiscoveryErrors.invalid_pagination("defaultPageSize must not exceed maxPageSize")

    def is_enabled(self, surface: DiscoverySurface) -> bool:
        return {
            DiscoverySurface.OPENAI_MODELS: self.enable_openai_models,
            DiscoverySurface.ANTHROPIC_MODELS: self.enable_anthropic_models,
            DiscoverySurface.AGENT_CARD: self.enable_agent_card,
        }[surface]

    def require_enabled(self, surface: DiscoverySurface) -> None:
        if not self.is_enabled(surface):
            raise DiscoveryErrors.surface_disabled(str(surface))

    @property
    def any_model_surface_enabled(self) -> bool:
        return self.enable_openai_models or self.enable_anthropic_models

    @classmethod
    def from_dict(cls, source: Mapping[str, Any]) -> DiscoveryConfiguration:
        raw_selection = source.get("dialectSelection")
        return cls(
            enable_openai_models=bool(source.get("enableOpenAiModels", False)),
            enable_anthropic_models=bool(source.get("enableAnthropicModels", False)),
            enable_agent_card=bool(source.get("enableAgentCard", False)),
            dialect_selection=(
                DialectSelection(str(raw_selection)) if raw_selection is not None else DialectSelection.HEADER
            ),
            require_authentication=bool(source.get("requireAuthentication", False)),
            default_page_size=int(source.get("defaultPageSize", DEFAULT_PAGE_SIZE)),
            max_page_size=int(source.get("maxPageSize", MAX_PAGE_SIZE)),
            external_base_url=_optional_str(source.get("externalBaseUrl")),
            route_prefix=str(source.get("routePrefix", "")),
        )


class DiscoveryService:
    """Serves the model discovery surfaces from the descriptor registry.

    Identifier matching is exact and case-sensitive, and a padded identifier is
    rejected rather than trimmed: silently accepting ``" agent "`` would make the
    advertised identifier and the accepted identifier two different things.
    """

    def __init__(
        self,
        registry: DescriptorRegistry,
        configuration: DiscoveryConfiguration | None = None,
    ) -> None:
        self._registry = registry
        self._configuration = configuration or DiscoveryConfiguration()
        self._dialect_selector = DialectSelector(self._configuration.dialect_selection)
        self._pagination = DiscoveryPagination(
            default_page_size=self._configuration.default_page_size,
            max_page_size=self._configuration.max_page_size,
        )

    @property
    def configuration(self) -> DiscoveryConfiguration:
        return self._configuration

    def select_dialect(self, headers: Mapping[str, Any] | None) -> ProviderDialect:
        return self._dialect_selector.select(headers)

    def list_models(
        self,
        *,
        headers: Mapping[str, Any] | None = None,
        dialect: ProviderDialect | None = None,
        pagination: PaginationRequest | None = None,
        descriptors: Sequence[AgentDescriptor] | None = None,
    ) -> dict[str, Any]:
        """Render the model listing in the resolved dialect.

        An empty catalogue is a successful empty listing, never an error.
        """

        resolved = dialect or self.select_dialect(headers)
        self._require_dialect_enabled(resolved)

        catalogue = tuple(descriptors) if descriptors is not None else self._registry.list_discoverable()

        if resolved is ProviderDialect.OPENAI:
            return OpenAiModelProjection.project_list(catalogue)

        page = self._pagination.paginate(
            catalogue,
            pagination or PaginationRequest(),
            lambda descriptor: descriptor.agent_id,
        )
        return AnthropicModelProjection.project_page(page)

    def get_model(
        self,
        agent_id: str,
        *,
        headers: Mapping[str, Any] | None = None,
        dialect: ProviderDialect | None = None,
        descriptors: Sequence[AgentDescriptor] | None = None,
    ) -> dict[str, Any]:
        """Retrieve a single model entry by exact, case-sensitive identifier."""

        resolved = dialect or self.select_dialect(headers)
        self._require_dialect_enabled(resolved)

        descriptor = self._find_visible(agent_id, descriptors)
        if descriptor is None:
            raise DiscoveryErrors.agent_not_found(agent_id)

        if resolved is ProviderDialect.OPENAI:
            return OpenAiModelProjection.project(descriptor)
        return AnthropicModelProjection.project(descriptor)

    def _find_visible(
        self,
        agent_id: str,
        descriptors: Sequence[AgentDescriptor] | None,
    ) -> AgentDescriptor | None:
        if agent_id != agent_id.strip():
            return None

        if descriptors is not None:
            return next((item for item in descriptors if item.agent_id == agent_id), None)

        descriptor = self._registry.find(agent_id)
        if descriptor is None or not descriptor.is_listed:
            return None
        return descriptor

    def _require_dialect_enabled(self, dialect: ProviderDialect) -> None:
        surface = (
            DiscoverySurface.OPENAI_MODELS
            if dialect is ProviderDialect.OPENAI
            else DiscoverySurface.ANTHROPIC_MODELS
        )
        self._configuration.require_enabled(surface)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None

"""Provider dialect selection for the shared model listing path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Mapping

from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors

ANTHROPIC_VERSION_HEADER: Final[str] = "anthropic-version"
SUPPORTED_ANTHROPIC_VERSIONS: Final[frozenset[str]] = frozenset({"2023-06-01"})


class ProviderDialect(StrEnum):
    """Wire dialect a discovery response is rendered in."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class DialectSelection(StrEnum):
    """How the runtime picks a dialect on the shared listing path."""

    HEADER = "header"
    OPENAI_ONLY = "openai_only"
    ANTHROPIC_ONLY = "anthropic_only"


@dataclass(slots=True)
class DialectSelector:
    """Resolves the dialect for a request.

    On the shared ``/v1/models`` path the Anthropic protocol version header is the
    discriminator, because it is the only signal an Anthropic client always sends
    and an OpenAI client never does. Absent the header the OpenAI dialect is the
    documented default. Configuration can pin a single dialect instead.
    """

    selection: DialectSelection = DialectSelection.HEADER

    def select(self, headers: Mapping[str, Any] | None) -> ProviderDialect:
        if self.selection is DialectSelection.OPENAI_ONLY:
            return ProviderDialect.OPENAI
        if self.selection is DialectSelection.ANTHROPIC_ONLY:
            return ProviderDialect.ANTHROPIC

        version = self._anthropic_version(headers)
        if version is None:
            return ProviderDialect.OPENAI

        if version not in SUPPORTED_ANTHROPIC_VERSIONS:
            raise DiscoveryErrors.unsupported_provider_version(version)

        return ProviderDialect.ANTHROPIC

    @staticmethod
    def _anthropic_version(headers: Mapping[str, Any] | None) -> str | None:
        if headers is None:
            return None

        value: object = None
        getter = getattr(headers, "get", None)
        if callable(getter):
            value = getter(ANTHROPIC_VERSION_HEADER)
            if value is None:
                value = getter(ANTHROPIC_VERSION_HEADER.title())

        if not isinstance(value, str) or not value.strip():
            return None

        return value.strip()

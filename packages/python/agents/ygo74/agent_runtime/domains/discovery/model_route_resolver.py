"""Resolution of an advertised model identifier back to its internal route key."""

from __future__ import annotations

from dataclasses import dataclass

from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry


@dataclass(slots=True)
class ModelRouteResolver:
    """Maps the identifier advertised by discovery onto the route key used for dispatch.

    Discovery advertises ``agentId`` while dispatch is keyed by ``routeKey``. This
    resolver closes the loop so a client can send back, verbatim, the identifier it
    read from a listing. Matching is exact: an identifier that does not correspond
    to a known agent resolves to ``None`` so the caller can fall back to its own
    default rather than being routed somewhere unintended.

    Args:
        registry (DescriptorRegistry): The registry that supplies the configured entries for this operation.
    """
    registry: DescriptorRegistry

    def route_key_for(self, model: object) -> str | None:
        """Resolve the configured route key that receives a request naming this public agent ID.

        Args:
            model (object): Provider-visible model or agent identifier.
        """
        if not isinstance(model, str) or not model:
            return None

        descriptor = self.registry.find(model)
        return None if descriptor is None else descriptor.route_key

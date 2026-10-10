"""Anthropic-style cursor pagination over the ordered descriptor catalogue."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

TItem = TypeVar("TItem")


@dataclass(slots=True, frozen=True)
class PaginationRequest:
    """Requested page window, expressed with Anthropic cursor semantics.

    Args:
        limit (int | None): The maximum number of entries or units permitted by this operation.
        after_id (str | None): Cursor requesting entries after this identifier.
        before_id (str | None): Cursor requesting entries before this identifier.
    """
    limit: int | None = None
    after_id: str | None = None
    before_id: str | None = None


@dataclass(slots=True, frozen=True)
class PaginationResult(Generic[TItem]):
    """One page plus the continuation indicators clients need to iterate.

    Args:
        items (tuple[TItem, ...]): The ordered collection to process or project.
        first_id (str | None): Identifier of the first item in the current page.
        last_id (str | None): Identifier of the last item in the current page.
        has_more (bool): Whether entries remain after the current page.
    """
    items: tuple[TItem, ...]
    first_id: str | None
    last_id: str | None
    has_more: bool


@dataclass(slots=True)
class DiscoveryPagination:
    """Applies cursor pagination to an already ordered collection.

    Cursors are entry identifiers rather than offsets, so a page boundary stays
    meaningful even when the catalogue changes between requests.

    Args:
        default_page_size (int): Page size used when the client omits a limit.
        max_page_size (int): Largest page size accepted from a discovery client.
    """
    default_page_size: int = DEFAULT_PAGE_SIZE
    max_page_size: int = MAX_PAGE_SIZE

    def __post_init__(self) -> None:
        """Validate and normalize the instance discovery entries after its generated initializer has assigned the fields.
        """
        if self.default_page_size < 1 or self.max_page_size < 1:
            raise DiscoveryErrors.invalid_pagination("page sizes must be positive")
        if self.default_page_size > self.max_page_size:
            raise DiscoveryErrors.invalid_pagination("defaultPageSize must not exceed maxPageSize")

    def paginate(
        self,
        items: Sequence[TItem],
        request: PaginationRequest,
        identity: Callable[[TItem], str],
    ) -> PaginationResult[TItem]:
        """Build a page discovery entries from the ordered entries and requested continuation position.

        Args:
            items (Sequence[TItem]): The ordered collection to process or project.
            request (PaginationRequest): The request received at this layer, with its protocol-specific or normalized fields.
            identity (Callable[[TItem], str]): Identifier required to correlate a route, content item, tool call, or user.
        """
        limit = self._resolve_limit(request.limit)
        identifiers = [identity(item) for item in items]

        start = 0
        end = len(items)

        if request.after_id is not None:
            start = self._index_of(identifiers, request.after_id, "after_id") + 1
        if request.before_id is not None:
            end = self._index_of(identifiers, request.before_id, "before_id")

        if start > end:
            raise DiscoveryErrors.invalid_pagination("after_id must precede before_id")

        window = tuple(items[start:end])

        # `before_id` walks the catalogue backwards, so the page is the block of
        # entries immediately preceding the cursor rather than the first block of
        # the window. `after_id` always wins when both cursors are supplied.
        walks_backwards = request.before_id is not None and request.after_id is None
        page = window[-limit:] if walks_backwards else window[:limit]
        has_more = len(window) > len(page)

        return PaginationResult(
            items=page,
            first_id=identity(page[0]) if page else None,
            last_id=identity(page[-1]) if page else None,
            has_more=has_more,
        )

    def _resolve_limit(self, requested: int | None) -> int:
        """Clamp or default the requested page size within the configured maximum.

        Args:
            requested (int | None): Requested value before applying pagination defaults or limits.
        """
        if requested is None:
            return self.default_page_size
        if requested < 1:
            raise DiscoveryErrors.invalid_pagination("limit must be at least 1")
        if requested > self.max_page_size:
            raise DiscoveryErrors.invalid_pagination(f"limit must not exceed {self.max_page_size}")
        return requested

    @staticmethod
    def _index_of(identifiers: list[str], cursor: str, parameter: str) -> int:
        """Find the descriptor position matching a pagination cursor, returning no index when absent.

        Args:
            identifiers (list[str]): Model identifiers included in or compared with the discovery listing.
            cursor (str): Opaque provider pagination cursor supplied by the client.
            parameter (str): Name of the query parameter being validated.
        """
        try:
            return identifiers.index(cursor)
        except ValueError as exc:
            raise DiscoveryErrors.invalid_pagination(f"{parameter} '{cursor}' is not a known entry") from exc

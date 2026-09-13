"""Anthropic-style cursor pagination over the ordered descriptor catalogue."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(slots=True, frozen=True)
class PaginationRequest:
    """Requested page window, expressed with Anthropic cursor semantics."""

    limit: int | None = None
    after_id: str | None = None
    before_id: str | None = None


@dataclass(slots=True, frozen=True)
class PaginationResult[TItem]:
    """One page plus the continuation indicators clients need to iterate."""

    items: tuple[TItem, ...]
    first_id: str | None
    last_id: str | None
    has_more: bool


@dataclass(slots=True)
class DiscoveryPagination:
    """Applies cursor pagination to an already ordered collection.

    Cursors are entry identifiers rather than offsets, so a page boundary stays
    meaningful even when the catalogue changes between requests.
    """

    default_page_size: int = DEFAULT_PAGE_SIZE
    max_page_size: int = MAX_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.default_page_size < 1 or self.max_page_size < 1:
            raise DiscoveryErrors.invalid_pagination("page sizes must be positive")
        if self.default_page_size > self.max_page_size:
            raise DiscoveryErrors.invalid_pagination("defaultPageSize must not exceed maxPageSize")

    def paginate[TItem](
        self,
        items: Sequence[TItem],
        request: PaginationRequest,
        identity: Callable[[TItem], str],
    ) -> PaginationResult[TItem]:
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
        if requested is None:
            return self.default_page_size
        if requested < 1:
            raise DiscoveryErrors.invalid_pagination("limit must be at least 1")
        if requested > self.max_page_size:
            raise DiscoveryErrors.invalid_pagination(f"limit must not exceed {self.max_page_size}")
        return requested

    @staticmethod
    def _index_of(identifiers: list[str], cursor: str, parameter: str) -> int:
        try:
            return identifiers.index(cursor)
        except ValueError as exc:
            raise DiscoveryErrors.invalid_pagination(f"{parameter} '{cursor}' is not a known entry") from exc

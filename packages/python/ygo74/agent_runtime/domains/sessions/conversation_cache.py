"""Keeping one conversation's state, without keeping everybody's forever.

A console session builds an agent once and lives as long as the process. An HTTP
surface cannot: each request is separate, yet a conversation must continue, so
something has to hold the agent, its history and its open connections between two
requests.

That something is dangerous in four specific ways, and this class exists to
address all four:

* **Confusion.** State is keyed by the *authenticated subject* first. A caller
  supplying somebody else's conversation identifier gets their own conversation,
  never that person's, because the key they control is only half of it.
* **Leaking.** Entries expire when idle and the cache is bounded, so a public
  endpoint cannot be made to accumulate agents indefinitely.
* **Dangling resources.** An evicted entry holds a live session. Dropping the
  reference would leak the connection, so eviction closes it.
* **Closing what is in use.** Eviction and expiry must not close a runtime a
  request is still working with. That is why :meth:`lease` is a context manager
  rather than a getter: an entry is held for exactly as long as somebody is using
  it, and a held entry is never closed.

The last point is the one that is easy to get wrong, because a laboratory running
one conversation at a bound of two hundred will never see it, while a deployment
choosing tighter bounds sees it immediately.

Two rules govern the lock, for the same kind of reason. Entries are added and
removed while it is held; builds and closers are awaited *outside* it. Closing a
session talks to a remote server, and awaiting that under a global lock lets one
unresponsive server stall every conversation in the process.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal

DEFAULT_IDLE_LIFETIME = timedelta(minutes=30)
DEFAULT_MAX_CONVERSATIONS = 200

RuntimeT = TypeVar("RuntimeT")

Clock = Callable[[], datetime]

_logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return the current instant, always timezone-aware."""
    return datetime.now(UTC)


@dataclass(slots=True)
class _Entry(Generic[RuntimeT]):
    """One conversation's runtime, when it was last used, and who is using it."""

    build: asyncio.Future[RuntimeT]
    last_used: datetime
    leases: int = field(default=0)

    def touch(self, now: datetime) -> None:
        """Record that this conversation is still alive."""
        self.last_used = now

    @property
    def is_idle(self) -> bool:
        """Whether nobody is currently working with this runtime."""
        return self.leases == 0


class ConversationRuntimeCache(Generic[RuntimeT]):
    """Holds one runtime per conversation, per authenticated subject.

    Args:
        factory: Builds the runtime of a conversation. Awaited once per entry,
            even when several requests race for the same conversation.
        closer: Releases a runtime. Called on eviction, on expiry and on
            shutdown, because a runtime holds a live session.
        max_conversations: Upper bound on live conversations. Reaching it evicts
            the least recently used *idle* conversation, which is a bounded
            service degrading rather than a process growing without limit.
        idle_lifetime: How long an untouched conversation is kept.
        clock: Injected so expiry is testable without waiting.
    """

    def __init__(
        self,
        factory: Callable[[AgentPrincipal, str], Awaitable[RuntimeT]],
        closer: Callable[[RuntimeT], Awaitable[None]],
        *,
        max_conversations: int = DEFAULT_MAX_CONVERSATIONS,
        idle_lifetime: timedelta = DEFAULT_IDLE_LIFETIME,
        clock: Clock = _utc_now,
    ) -> None:
        if max_conversations < 1:
            raise ValueError("a cache holding no conversation cannot serve one")
        self._factory = factory
        self._closer = closer
        self._max_conversations = max_conversations
        self._idle_lifetime = idle_lifetime
        self._clock = clock
        self._entries: dict[tuple[str, str], _Entry[RuntimeT]] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def lease(self, principal: AgentPrincipal, conversation_id: str) -> AsyncIterator[RuntimeT]:
        """Borrow the runtime of a conversation for the duration of a block.

        Concurrent callers of the same conversation share one build. A model
        routinely triggers overlapping work, and building twice would open two
        sessions and silently discard one.

        While the block runs, the entry cannot be evicted or expired. That is the
        whole point: a getter would hand out a runtime and let the next request
        close it mid-use.
        """
        key = (principal.subject, conversation_id)
        build, evicted = await self._borrow(principal, conversation_id)
        await self._release_all(evicted)

        try:
            runtime = await build
        except BaseException:
            # A failed build must not be cached: the next request deserves a
            # fresh attempt rather than the same exception for half an hour.
            await self._discard(key)
            raise

        try:
            yield runtime
        finally:
            await self._return(key)

    async def release(self, principal: AgentPrincipal, conversation_id: str) -> None:
        """Close and forget one conversation."""
        entry = await self._detach((principal.subject, conversation_id))
        await self._release_all([entry] if entry is not None else [])

    async def aclose(self) -> None:
        """Close every live conversation, on shutdown."""
        async with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
        await self._release_all(entries)

    @property
    def live_conversations(self) -> int:
        """How many conversations are currently held."""
        return len(self._entries)

    async def _borrow(
        self,
        principal: AgentPrincipal,
        conversation_id: str,
    ) -> tuple[asyncio.Future[RuntimeT], list[_Entry[RuntimeT]]]:
        """Take a lease under the lock, and report what fell out of the cache.

        Nothing is awaited here beyond the lock itself: the entries to close are
        handed back so the caller can release them outside it.
        """
        key = (principal.subject, conversation_id)
        async with self._lock:
            now = self._clock()
            evicted = self._expire(now)
            entry = self._entries.get(key)
            if entry is None:
                # `ensure_future` rather than `create_task`: the factory is typed
                # as returning an awaitable, and a future can be awaited by every
                # caller that races for this conversation.
                entry = _Entry(
                    build=asyncio.ensure_future(self._factory(principal, conversation_id)),
                    last_used=now,
                )
                self._entries[key] = entry
                evicted.extend(self._enforce_bound())
            else:
                entry.touch(now)
            entry.leases += 1
            return entry.build, evicted

    async def _return(self, key: tuple[str, str]) -> None:
        """Give back a lease once the caller is done with the runtime."""
        async with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.leases > 0:
                entry.leases -= 1

    async def _discard(self, key: tuple[str, str]) -> None:
        """Drop an entry whose build failed, without closing anything."""
        async with self._lock:
            self._entries.pop(key, None)

    async def _detach(self, key: tuple[str, str]) -> _Entry[RuntimeT] | None:
        """Remove one entry from the cache and hand it back to be closed."""
        async with self._lock:
            return self._entries.pop(key, None)

    def _expire(self, now: datetime) -> list[_Entry[RuntimeT]]:
        """Take out the conversations nobody has touched, or is using, for a while.

        A leased entry is skipped rather than closed. It is reconsidered on the
        next pass, by which time its lease will have been returned.
        """
        deadline = now - self._idle_lifetime
        stale = [key for key, entry in self._entries.items() if entry.is_idle and entry.last_used <= deadline]
        return [self._entries.pop(key) for key in stale]

    def _enforce_bound(self) -> list[_Entry[RuntimeT]]:
        """Keep the number of live conversations under the configured ceiling.

        Only an idle conversation may be evicted. When every conversation is in
        use the cache is allowed to exceed its bound for as long as that lasts:
        serving slightly more than asked is a bounded overshoot, whereas closing a
        runtime somebody is using is a broken turn.
        """
        taken: list[_Entry[RuntimeT]] = []
        while len(self._entries) > self._max_conversations:
            idle = [key for key, entry in self._entries.items() if entry.is_idle]
            if not idle:
                _logger.warning(
                    "every conversation is in use; staying above the bound of %d until one is released",
                    self._max_conversations,
                )
                break
            oldest = min(idle, key=lambda key: self._entries[key].last_used)
            _logger.info("evicting the least recently used conversation to stay within bounds")
            taken.append(self._entries.pop(oldest))
        return taken

    async def _release_all(self, entries: list[_Entry[RuntimeT]]) -> None:
        """Release entries that are already out of the cache, off the lock."""
        for entry in entries:
            await self._close(entry)

    async def _close(self, entry: _Entry[RuntimeT]) -> None:
        """Release a runtime, tolerating one that never finished building.

        Shutting down must not raise: whatever went wrong, the entry is already
        gone from the cache and nothing can reach it any more.
        """
        try:
            runtime = await entry.build
        except Exception as error:  # noqa: BLE001 - a build that failed holds nothing to close
            _logger.debug("discarded a conversation that never built: %s", type(error).__name__)
            return

        try:
            await self._closer(runtime)
        except Exception as error:  # noqa: BLE001 - see the docstring
            _logger.warning("could not release a conversation: %s", type(error).__name__)

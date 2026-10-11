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
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar
from uuid import uuid4

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal

from .continuity_diagnostics import ContinuityDiagnostics

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
    """One conversation's runtime, when it was last used, and who is using it.

    Args:
        build (asyncio.Future[RuntimeT]): In-progress task that creates the runtime for a cache entry.
        last_used (datetime): Timestamp used to evict the least recently used idle conversation.
        leases (int): Number of active users holding the conversation entry.
        execution: Serializes turns after borrowers have pinned the entry.
        invalidated: Failed native state that must be retired after leases drain.
        instance: Opaque runtime entry instance.
        identity_fingerprint: Process-local verified identity correlation.
        conversation_fingerprint: Process-local conversation correlation.
    """
    build: asyncio.Future[RuntimeT]
    last_used: datetime
    leases: int = field(default=0)
    execution: asyncio.Lock = field(default_factory=asyncio.Lock)
    invalidated: bool = False
    instance: str = field(default_factory=lambda: uuid4().hex)
    identity_fingerprint: str = ""
    conversation_fingerprint: str = ""

    def touch(self, now: datetime) -> None:
        """Record that this conversation is still alive.

        Args:
            now (datetime): Current time used to evaluate expiry and ordering.
        """
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
        identity_namespace: Operator issuer/tenant partition for this cache.
        hard_capacity: Reject new busy conversations rather than exceed capacity.
    """
    def __init__(
        self,
        factory: Callable[[AgentPrincipal, str], Awaitable[RuntimeT]],
        closer: Callable[[RuntimeT], Awaitable[None]],
        *,
        max_conversations: int = DEFAULT_MAX_CONVERSATIONS,
        idle_lifetime: timedelta = DEFAULT_IDLE_LIFETIME,
        clock: Clock = _utc_now,
        identity_namespace: str = "",
        hard_capacity: bool = False,
    ) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            factory (Callable[[AgentPrincipal, str], Awaitable[RuntimeT]]): Factory that creates or retrieves the requested runtime component.
            closer (Callable[[RuntimeT], Awaitable[None]]): Async callback that releases a runtime after eviction.
            max_conversations (int): Target upper bound for retained conversation runtimes.
            idle_lifetime (timedelta): Maximum age of an unused conversation before eviction.
            clock (Clock): Clock used to make expiry and time-based behavior deterministic.
            identity_namespace: Operator-selected issuer/tenant partition.
            hard_capacity: Whether busy entries cause admission rejection.
        """
        if max_conversations < 1:
            raise ValueError("a cache holding no conversation cannot serve one")
        self._factory = factory
        self._closer = closer
        self._max_conversations = max_conversations
        self._idle_lifetime = idle_lifetime
        self._clock = clock
        self._identity_namespace = identity_namespace
        self._hard_capacity = hard_capacity
        self._entries: dict[tuple[str, str], _Entry[RuntimeT]] = {}
        self._lock = asyncio.Lock()
        self._drained = asyncio.Condition(self._lock)
        self._closed = False
        self._retiring: set[asyncio.Task[None]] = set()

    def _key(self, principal: AgentPrincipal, conversation_id: str) -> tuple[str, str]:
        """Partition state by verified identity, including refreshed claims.

        Args:
            principal: Verified caller; changed email/roles require fresh resources.
            conversation_id: Caller handle within the operator namespace.
        """
        identity = json.dumps(
            (principal.subject, principal.email, principal.display_name, sorted(principal.roles)),
            separators=(",", ":"),
        )
        return (self._identity_namespace + ":" + identity, conversation_id)

    @asynccontextmanager
    async def turn(self, principal: AgentPrincipal, conversation_id: str) -> AsyncIterator[RuntimeT]:
        """Serialize a turn while pinning both queued and active work.

        Args:
            principal: Verified caller whose claims select the resources.
            conversation_id: Conversation whose turns must not overlap.
        """
        async with self.lease(principal, conversation_id) as runtime:
            entry = self._entries[self._key(principal, conversation_id)]
            async with entry.execution:
                if entry.invalidated:
                    raise RuntimeError("conversation was invalidated")
                try:
                    yield runtime
                except BaseException:
                    entry.invalidated = True
                    self._diagnose(entry, "invalidate", reason="turn_error_or_cancel")
                    raise

    async def invalidate(self, principal: AgentPrincipal, conversation_id: str) -> None:
        """Prevent failed native state from being reused; close after leases drain.

        Args:
            principal: Verified caller whose resources failed.
            conversation_id: Affected conversation.
        """
        async with self._lock:
            entry = self._entries.get(self._key(principal, conversation_id))
            if entry is not None:
                entry.invalidated = True
                self._diagnose(entry, "invalidate", reason="explicit")

    @asynccontextmanager
    async def lease(self, principal: AgentPrincipal, conversation_id: str) -> AsyncIterator[RuntimeT]:
        """Borrow the runtime of a conversation for the duration of a block.

        Concurrent callers of the same conversation share one build. A model
        routinely triggers overlapping work, and building twice would open two
        sessions and silently discard one.

        While the block runs, the entry cannot be evicted or expired. That is the
        whole point: a getter would hand out a runtime and let the next request
        close it mid-use.

        Args:
            principal (AgentPrincipal): Authenticated principal whose identity and claims are being projected.
            conversation_id (str): Conversation identity used to select session state for this caller.
        """
        key = self._key(principal, conversation_id)
        build, evicted = await self._borrow(principal, conversation_id)
        try:
            await self._release_all(evicted)
            # One cancelled waiter must not cancel another caller's shared build.
            runtime = await asyncio.shield(build)
            yield runtime
        finally:
            await self._return(key)
            if build.done() and (build.cancelled() or build.exception() is not None):
                await self._discard(key)

    async def release(self, principal: AgentPrincipal, conversation_id: str) -> None:
        """Close and forget one conversation.

        Args:
            principal (AgentPrincipal): Authenticated principal whose identity and claims are being projected.
            conversation_id (str): Conversation identity used to select session state for this caller.
        """
        entry = await self._detach(self._key(principal, conversation_id))
        await self._release_all([entry] if entry is not None else [])

    async def aclose(self) -> None:
        """Close every live conversation, on shutdown."""
        async with self._lock:
            self._closed = True
            # Stop admission before draining; never close a queued/active turn.
            await self._drained.wait_for(
                lambda: not self._retiring and all(entry.is_idle for entry in self._entries.values())
            )
            entries = list(self._entries.values())
            for entry in entries:
                self._diagnose(entry, "release", reason="shutdown")
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

        Successful admission hands detached entries back to the caller. Rejected
        admission closes them here, outside the lock, before propagating errors.

        Args:
            principal (AgentPrincipal): Authenticated principal whose identity and claims are being projected.
            conversation_id (str): Conversation identity used to select session state for this caller.
        """
        key = self._key(principal, conversation_id)
        evicted: list[_Entry[RuntimeT]] = []
        try:
            async with self._lock:
                if self._closed:
                    raise RuntimeError("conversation cache is shutting down")
                now = self._clock()
                evicted = self._expire(now)
                entry = self._entries.get(key)
                if entry is not None and entry.invalidated:
                    raise RuntimeError("conversation was invalidated and is draining")
                if entry is None:
                    if (self._hard_capacity and len(self._entries) >= self._max_conversations
                            and not any(candidate.is_idle for candidate in self._entries.values())):
                        raise RuntimeError("conversation capacity is exhausted")
                    # A factory returns an awaitable, potentially a shared future.
                    entry = _Entry(
                        build=asyncio.ensure_future(self._factory(principal, conversation_id)),
                        last_used=now,
                        identity_fingerprint=ContinuityDiagnostics.fingerprint(key[0]),
                        conversation_fingerprint=ContinuityDiagnostics.fingerprint(key[1]),
                    )
                    self._entries[key] = entry
                    self._diagnose(entry, "create", reason="cache_miss")
                else:
                    entry.touch(now)
                    self._diagnose(entry, "hit")
                entry.leases += 1
                evicted.extend(self._enforce_bound())
                return entry.build, evicted
        except BaseException:
            # Detached expiry resources remain our responsibility on every
            # rejection path, even though lease() never receives their list.
            retirements = [self._start_retirement(entry) for entry in evicted]
            if retirements:
                await asyncio.shield(asyncio.gather(*retirements))
            raise

    async def _return(self, key: tuple[str, str]) -> None:
        """Give back a lease once the caller is done with the runtime.

        Args:
            key (tuple[str, str]): The identifier used to locate the corresponding registered value.
        """
        retirement: asyncio.Task[None] | None = None
        async with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.leases > 0:
                entry.leases -= 1
                entry.touch(self._clock())
                if entry.is_idle and entry.invalidated:
                    retired = self._entries.pop(key)
                    self._diagnose(retired, "release", reason="invalidated")
                    retirement = self._start_retirement(retired)
                self._drained.notify_all()
        if retirement is not None:
            # A second caller cancellation must not interrupt dependency cleanup.
            await asyncio.shield(retirement)

    def _start_retirement(self, entry: _Entry[RuntimeT]) -> asyncio.Task[None]:
        """Track detached cleanup before yielding control to callers or shutdown.

        Args:
            entry: Detached resource whose cleanup must survive cancellation.
        """
        retirement = asyncio.create_task(self._retire(entry))
        self._retiring.add(retirement)
        return retirement

    async def _retire(self, entry: _Entry[RuntimeT]) -> None:
        """Keep invalidated resource cleanup visible to shutdown until complete.

        Args:
            entry: Invalidated idle entry already removed from admission.
        """
        try:
            await self._close(entry)
        finally:
            async with self._lock:
                task = asyncio.current_task()
                if task is not None:
                    self._retiring.discard(task)
                self._drained.notify_all()

    async def _discard(self, key: tuple[str, str]) -> None:
        """Drop an entry whose build failed, without closing anything.

        Args:
            key (tuple[str, str]): The identifier used to locate the corresponding registered value.
        """
        async with self._lock:
            entry = self._entries.pop(key, None)
            if entry is not None:
                self._diagnose(entry, "release", reason="build_failed")

    async def _detach(self, key: tuple[str, str]) -> _Entry[RuntimeT] | None:
        """Remove one entry from the cache and hand it back to be closed.

        Args:
            key (tuple[str, str]): The identifier used to locate the corresponding registered value.
        """
        async with self._lock:
            entry = self._entries.get(key)
            if entry is not None and not entry.is_idle:
                raise RuntimeError("cannot release a conversation during a turn")
            entry = self._entries.pop(key, None)
            if entry is not None:
                self._diagnose(entry, "release", reason="explicit")
            return entry

    def _expire(self, now: datetime) -> list[_Entry[RuntimeT]]:
        """Take out the conversations nobody has touched, or is using, for a while.

        A leased entry is skipped rather than closed. It is reconsidered on the
        next pass, by which time its lease will have been returned.

        Args:
            now (datetime): Current time used to evaluate expiry and ordering.
        """
        deadline = now - self._idle_lifetime
        stale = [key for key, entry in self._entries.items() if entry.is_idle and entry.last_used <= deadline]
        expired = [self._entries.pop(key) for key in stale]
        for entry in expired:
            self._diagnose(entry, "expire", reason="idle_lifetime")
        return expired

    def _enforce_bound(self) -> list[_Entry[RuntimeT]]:
        """Keep the number of live conversations under the configured ceiling.

        Only an idle conversation may be evicted. When every conversation is in
        use the cache is allowed to exceed its bound for as long as that lasts:
        serving slightly more than asked is a bounded overshoot, whereas closing a
        runtime somebody is using is a broken turn.
        """
        # Evict the least-recently-used idle entry while over capacity; if every entry is leased, preserve active work and temporarily allow the cache to exceed its bound.
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
            entry = self._entries.pop(oldest)
            self._diagnose(entry, "evict", reason="capacity")
            taken.append(entry)
        return taken

    @staticmethod
    def _diagnose(entry: _Entry[RuntimeT], phase: str, *, reason: str | None = None) -> None:
        """Record cache routing without exposing keys or identity claims.

        Args:
            entry: Cache resource with precomputed safe correlations.
            phase: Trusted lifecycle event.
            reason: Trusted recreation/retirement reason.
        """
        ContinuityDiagnostics.record(
            _logger, "conversation cache continuity", phase=phase, reason=reason,
            cache_instance=entry.instance, identity_fingerprint=entry.identity_fingerprint,
            conversation_fingerprint=entry.conversation_fingerprint,
        )

    async def _release_all(self, entries: list[_Entry[RuntimeT]]) -> None:
        """Release entries that are already out of the cache, off the lock.

        Args:
            entries (list[_Entry[RuntimeT]]): Conversation cache entries considered for release or eviction.
        """
        for entry in entries:
            await self._close(entry)

    async def _close(self, entry: _Entry[RuntimeT]) -> None:
        """Release a runtime, tolerating one that never finished building.

        Shutting down must not raise: whatever went wrong, the entry is already
        gone from the cache and nothing can reach it any more.

        Args:
            entry (_Entry[RuntimeT]): State or registry entry currently being processed.
        """
        try:
            runtime = await entry.build
        except asyncio.CancelledError:
            # A cancelled factory owns its cleanup; it produced no runtime.
            return
        except Exception as error:  # noqa: BLE001 - a build that failed holds nothing to close
            _logger.debug("discarded a conversation that never built: %s", type(error).__name__)
            return

        try:
            await self._closer(runtime)
        except Exception as error:  # noqa: BLE001 - see the docstring
            _logger.warning("could not release a conversation: %s", type(error).__name__)

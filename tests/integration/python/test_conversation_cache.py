"""Tests of the state a conversation keeps between two requests.

Holding an agent between requests is what makes a conversation possible and what
makes a public endpoint dangerous. Five failures matter: serving one person's
conversation to another, accumulating agents until the process dies, dropping a
live session without closing it, closing one that a request is still using, and
letting a single unresponsive server stall every conversation.

The last two are the reason this component was repaired before it shipped. They
are invisible at generous bounds and immediate at tight ones.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.sessions.conversation_cache import ConversationRuntimeCache

ADA = AgentPrincipal(subject="ada-3f9a", email="ada@example.com")
BOB = AgentPrincipal(subject="bob-77c1", email="bob@example.com")
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class FakeRuntime:
    """A runtime that records whether it was released."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.closed = False


class RuntimeFactory:
    """Builds fake runtimes and counts how often it was asked to."""

    def __init__(self, *, delay: float = 0.0, close_delay: float = 0.0) -> None:
        self.builds: list[tuple[str, str]] = []
        self.closed: list[FakeRuntime] = []
        self._delay = delay
        self._close_delay = close_delay

    async def build(self, principal: AgentPrincipal, conversation_id: str) -> FakeRuntime:
        """Build the runtime of one conversation."""
        self.builds.append((principal.subject, conversation_id))
        if self._delay:
            await asyncio.sleep(self._delay)
        return FakeRuntime(f"{principal.subject}:{conversation_id}")

    async def close(self, runtime: FakeRuntime) -> None:
        """Release a runtime, as the cache does on eviction."""
        if self._close_delay:
            await asyncio.sleep(self._close_delay)
        runtime.closed = True
        self.closed.append(runtime)


class MovableClock:
    """A clock the test advances by hand."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, amount: timedelta) -> None:
        """Move time forward."""
        self.now += amount


def build_cache(factory: RuntimeFactory, clock: MovableClock, **options: Any) -> ConversationRuntimeCache[FakeRuntime]:
    """Assemble a cache over the fake factory."""
    return ConversationRuntimeCache(factory.build, factory.close, clock=clock, **options)


async def label_of(cache: ConversationRuntimeCache[FakeRuntime], principal: AgentPrincipal, conversation: str) -> str:
    """Borrow a runtime and read its label, releasing it immediately."""
    async with cache.lease(principal, conversation) as runtime:
        return runtime.label


# ------------------------------------------------------- a conversation continues


def test_the_same_conversation_reuses_one_runtime() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        cache = build_cache(factory, MovableClock(NOW))

        async with cache.lease(ADA, "conv-1") as first:
            pass
        async with cache.lease(ADA, "conv-1") as second:
            pass

        assert first is second
        assert len(factory.builds) == 1

    asyncio.run(scenario())


def test_two_conversations_of_one_caller_are_separate() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        cache = build_cache(factory, MovableClock(NOW))

        first = await label_of(cache, ADA, "conv-1")
        second = await label_of(cache, ADA, "conv-2")

        assert first != second
        assert cache.live_conversations == 2

    asyncio.run(scenario())


def test_concurrent_callers_of_one_conversation_share_a_single_build() -> None:
    """Building twice would open two sessions and silently discard one."""

    async def scenario() -> None:
        factory = RuntimeFactory(delay=0.01)
        cache = build_cache(factory, MovableClock(NOW))

        results = await asyncio.gather(
            label_of(cache, ADA, "conv-1"),
            label_of(cache, ADA, "conv-1"),
            label_of(cache, ADA, "conv-1"),
        )

        assert len(set(results)) == 1
        assert len(factory.builds) == 1

    asyncio.run(scenario())


# ------------------------------------------------------------ callers are separate


def test_one_caller_never_reaches_another_conversation() -> None:
    """The identifier a caller controls is only half the key."""

    async def scenario() -> None:
        factory = RuntimeFactory()
        cache = build_cache(factory, MovableClock(NOW))

        ada = await label_of(cache, ADA, "conv-1")
        bob = await label_of(cache, BOB, "conv-1")

        assert ada != bob
        assert cache.live_conversations == 2

    asyncio.run(scenario())


def test_a_crafted_conversation_identifier_cannot_collide() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        cache = build_cache(factory, MovableClock(NOW))

        await label_of(cache, AgentPrincipal(subject="ada", email="a@b"), "3f9a:conv-1")
        await label_of(cache, AgentPrincipal(subject="ada:3f9a", email="a@b"), "conv-1")

        assert cache.live_conversations == 2

    asyncio.run(scenario())


# ----------------------------------------------------------------- bounded and idle


def test_an_untouched_conversation_expires_and_is_released() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        clock = MovableClock(NOW)
        cache = build_cache(factory, clock, idle_lifetime=timedelta(minutes=30))

        await label_of(cache, ADA, "conv-1")
        clock.advance(timedelta(minutes=31))
        await label_of(cache, BOB, "conv-2")

        assert cache.live_conversations == 1
        assert factory.closed[0].label.startswith("ada")

    asyncio.run(scenario())


def test_using_a_conversation_keeps_it_alive() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        clock = MovableClock(NOW)
        cache = build_cache(factory, clock, idle_lifetime=timedelta(minutes=30))

        await label_of(cache, ADA, "conv-1")
        clock.advance(timedelta(minutes=20))
        await label_of(cache, ADA, "conv-1")
        clock.advance(timedelta(minutes=20))
        await label_of(cache, BOB, "conv-2")

        assert cache.live_conversations == 2
        assert factory.closed == []

    asyncio.run(scenario())


def test_the_least_recently_used_conversation_is_evicted() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        clock = MovableClock(NOW)
        cache = build_cache(factory, clock, max_conversations=2)

        await label_of(cache, ADA, "conv-1")
        clock.advance(timedelta(minutes=1))
        await label_of(cache, ADA, "conv-2")
        clock.advance(timedelta(minutes=1))
        await label_of(cache, ADA, "conv-3")

        assert cache.live_conversations == 2
        assert [runtime.label for runtime in factory.closed] == ["ada-3f9a:conv-1"]

    asyncio.run(scenario())


def test_a_cache_holding_no_conversation_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot serve one"):
        ConversationRuntimeCache(RuntimeFactory().build, RuntimeFactory().close, max_conversations=0)


# ------------------------------------------------- what is in use is never closed


def test_a_leased_conversation_is_not_evicted() -> None:
    """The defect this component was repaired for.

    A getter hands out a runtime and forgets it; the next request can then evict
    and close the very object the first one is still working with.
    """

    async def scenario() -> None:
        factory = RuntimeFactory()
        clock = MovableClock(NOW)
        cache = build_cache(factory, clock, max_conversations=1)

        async with cache.lease(ADA, "conv-1") as held:
            clock.advance(timedelta(minutes=1))
            await label_of(cache, ADA, "conv-2")

            assert not held.closed
            assert held not in factory.closed

    asyncio.run(scenario())


def test_a_leased_conversation_is_not_expired() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        clock = MovableClock(NOW)
        cache = build_cache(factory, clock, idle_lifetime=timedelta(minutes=30))

        async with cache.lease(ADA, "conv-1") as held:
            clock.advance(timedelta(hours=2))
            await label_of(cache, BOB, "conv-2")

            assert not held.closed

    asyncio.run(scenario())


def test_a_conversation_is_evicted_once_its_lease_is_returned() -> None:
    """Held entries are skipped, not exempted: the next pass reconsiders them."""

    async def scenario() -> None:
        factory = RuntimeFactory()
        clock = MovableClock(NOW)
        cache = build_cache(factory, clock, max_conversations=1)

        async with cache.lease(ADA, "conv-1"):
            clock.advance(timedelta(minutes=1))
            await label_of(cache, ADA, "conv-2")

        clock.advance(timedelta(minutes=1))
        await label_of(cache, ADA, "conv-3")

        assert cache.live_conversations <= 2
        assert any(runtime.label == "ada-3f9a:conv-1" for runtime in factory.closed)

    asyncio.run(scenario())


def test_a_lease_is_returned_even_when_the_turn_raises() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        clock = MovableClock(NOW)
        cache = build_cache(factory, clock, max_conversations=1)

        with pytest.raises(RuntimeError):
            async with cache.lease(ADA, "conv-1"):
                raise RuntimeError("the turn failed")

        clock.advance(timedelta(minutes=1))
        await label_of(cache, ADA, "conv-2")

        assert any(runtime.label == "ada-3f9a:conv-1" for runtime in factory.closed)

    asyncio.run(scenario())


def test_a_slow_close_does_not_stall_another_conversation() -> None:
    """Closing talks to a remote server; awaiting it under the lock stalls everyone."""

    async def scenario() -> None:
        factory = RuntimeFactory(close_delay=0.05)
        clock = MovableClock(NOW)
        cache = build_cache(factory, clock, idle_lifetime=timedelta(minutes=30))

        await label_of(cache, ADA, "conv-1")
        clock.advance(timedelta(hours=1))

        # This acquisition expires Ada's conversation, so it pays the slow close.
        evicting = asyncio.create_task(label_of(cache, BOB, "conv-2"))
        await asyncio.sleep(0)

        # A third conversation must not be made to wait behind that close.
        started = asyncio.get_running_loop().time()
        await label_of(cache, BOB, "conv-3")
        waited = asyncio.get_running_loop().time() - started

        await evicting
        assert waited < 0.04, f"a slow close blocked an unrelated conversation for {waited:.3f}s"

    asyncio.run(scenario())


# ------------------------------------------------------------------ releasing


def test_shutdown_releases_every_conversation() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        cache = build_cache(factory, MovableClock(NOW))

        await label_of(cache, ADA, "conv-1")
        await label_of(cache, BOB, "conv-2")
        await cache.aclose()

        assert cache.live_conversations == 0
        assert len(factory.closed) == 2
        assert all(runtime.closed for runtime in factory.closed)

    asyncio.run(scenario())


def test_one_conversation_can_be_released_on_its_own() -> None:
    async def scenario() -> None:
        factory = RuntimeFactory()
        cache = build_cache(factory, MovableClock(NOW))

        await label_of(cache, ADA, "conv-1")
        await cache.release(ADA, "conv-1")

        assert cache.live_conversations == 0
        assert len(factory.closed) == 1

    asyncio.run(scenario())


def test_a_failed_build_is_not_cached() -> None:
    """The next request deserves a fresh attempt, not the same exception."""

    async def scenario() -> None:
        attempts: list[str] = []

        async def fail_once(principal: AgentPrincipal, conversation_id: str) -> FakeRuntime:
            attempts.append(conversation_id)
            if len(attempts) == 1:
                raise RuntimeError("transient")
            return FakeRuntime("recovered")

        cache: ConversationRuntimeCache[FakeRuntime] = ConversationRuntimeCache(
            fail_once,
            RuntimeFactory().close,
            clock=MovableClock(NOW),
        )

        with pytest.raises(RuntimeError):
            async with cache.lease(ADA, "conv-1"):
                pass

        assert await label_of(cache, ADA, "conv-1") == "recovered"
        assert cache.live_conversations == 1

    asyncio.run(scenario())


def test_a_closer_that_raises_does_not_break_shutdown() -> None:
    async def scenario() -> None:
        async def refuse(runtime: FakeRuntime) -> None:
            raise OSError("the server already went away")

        factory = RuntimeFactory()
        cache: ConversationRuntimeCache[FakeRuntime] = ConversationRuntimeCache(
            factory.build,
            refuse,
            clock=MovableClock(NOW),
        )

        await label_of(cache, ADA, "conv-1")
        await cache.aclose()

        assert cache.live_conversations == 0

    asyncio.run(scenario())

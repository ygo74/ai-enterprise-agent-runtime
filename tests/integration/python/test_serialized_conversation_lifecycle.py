"""Concurrency, cancellation and shutdown contracts for managed state."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.sessions.conversation_cache import (
    ConversationRuntimeCache,
)

PRINCIPAL = AgentPrincipal(subject="verified", roles=frozenset({"read"}))


async def build(principal, conversation):
    return SimpleNamespace(closed=False, principal=principal, conversation=conversation)


async def close(runtime):
    runtime.closed = True


@pytest.mark.asyncio
async def test_turns_serialize_without_blocking_other_conversations():
    cache = ConversationRuntimeCache(build, close)
    entered, release = asyncio.Event(), asyncio.Event()
    order = []
    async def first():
        async with cache.turn(PRINCIPAL, "one"):
            order.append(1)
            entered.set()
            await release.wait()
            order.append(2)
    async def second():
        async with cache.turn(PRINCIPAL, "one"):
            order.append(3)
    task = asyncio.create_task(first())
    await entered.wait()
    queued = asyncio.create_task(second())
    await asyncio.sleep(0)
    async with cache.turn(PRINCIPAL, "other"):
        assert order == [1]
    release.set()
    await asyncio.gather(task, queued)
    assert order == [1, 2, 3]
    await cache.aclose()


@pytest.mark.asyncio
async def test_shutdown_drains_and_stops_admission():
    cache = ConversationRuntimeCache(build, close)
    async with cache.turn(PRINCIPAL, "one") as runtime:
        shutdown = asyncio.create_task(cache.aclose())
        await asyncio.sleep(0)
        assert not runtime.closed and not shutdown.done()
        with pytest.raises(RuntimeError, match="shutting down"):
            async with cache.turn(PRINCIPAL, "two"):
                pass
    await shutdown
    assert runtime.closed


@pytest.mark.asyncio
async def test_cancelled_turn_closes_and_next_turn_is_fresh():
    cache = ConversationRuntimeCache(build, close)
    with pytest.raises(asyncio.CancelledError):
        async with cache.turn(PRINCIPAL, "one") as first:
            raise asyncio.CancelledError
    assert first.closed
    async with cache.turn(PRINCIPAL, "one") as second:
        assert second is not first
    await cache.aclose()


@pytest.mark.asyncio
async def test_refreshed_claims_do_not_reuse_cached_authorization():
    cache = ConversationRuntimeCache(build, close)
    async with cache.turn(PRINCIPAL, "one") as first:
        pass
    revoked = PRINCIPAL.model_copy(update={"roles": frozenset()})
    async with cache.turn(revoked, "one") as second:
        assert second is not first and not second.principal.roles
    await cache.aclose()


@pytest.mark.asyncio
async def test_managed_capacity_never_evicts_active_turn():
    cache = ConversationRuntimeCache(build, close, max_conversations=1, hard_capacity=True)
    async with cache.turn(PRINCIPAL, "one") as first:
        with pytest.raises(RuntimeError, match="capacity"):
            async with cache.turn(PRINCIPAL, "two"):
                pass
        assert not first.closed
    await cache.aclose()


@pytest.mark.asyncio
async def test_cancelled_factory_is_not_cached_or_reawaited_on_shutdown():
    async def cancelled(principal, conversation):
        raise asyncio.CancelledError
    cache = ConversationRuntimeCache(cancelled, close)
    with pytest.raises(asyncio.CancelledError):
        async with cache.turn(PRINCIPAL, "one"):
            pass
    assert cache.live_conversations == 0
    await cache.aclose()


@pytest.mark.asyncio
async def test_shutdown_waits_for_invalidated_scope_cleanup():
    closing, release = asyncio.Event(), asyncio.Event()
    async def delayed_close(runtime):
        closing.set()
        await release.wait()
        runtime.closed = True
    cache = ConversationRuntimeCache(build, delayed_close)
    async def failed_turn():
        with pytest.raises(RuntimeError, match="failure"):
            async with cache.turn(PRINCIPAL, "one"):
                raise RuntimeError("failure")
    failed = asyncio.create_task(failed_turn())
    await closing.wait()
    shutdown = asyncio.create_task(cache.aclose())
    await asyncio.sleep(0)
    assert not shutdown.done()
    release.set()
    await asyncio.gather(failed, shutdown)


@pytest.mark.asyncio
async def test_rejected_invalidated_borrow_still_closes_expired_runtimes():
    """Expiry cleanup survives admission rejection for another held runtime."""
    now = datetime(2026, 10, 10, tzinfo=UTC)
    cache = ConversationRuntimeCache(build, close, clock=lambda: now, idle_lifetime=timedelta(seconds=1))
    async with cache.lease(PRINCIPAL, "idle") as idle:
        pass
    async with cache.lease(PRINCIPAL, "held") as held:
        await cache.invalidate(PRINCIPAL, "held")
        now += timedelta(seconds=2)
        with pytest.raises(RuntimeError, match="invalidated"):
            async with cache.lease(PRINCIPAL, "held"):
                pass
        assert idle.closed
        assert not held.closed
    assert held.closed
    await cache.aclose()


@pytest.mark.asyncio
async def test_rejected_factory_still_closes_expired_runtimes():
    """Synchronous factory failure cannot lose detached expiry resources."""
    now = datetime(2026, 10, 10, tzinfo=UTC)
    def rejecting_factory(principal, conversation):
        """Reject one build before returning an awaitable.

        Args:
            principal: Verified identity used by the controlled builder.
            conversation: Conversation selected for construction.
        """
        if conversation == "reject":
            raise RuntimeError("factory rejected")
        return build(principal, conversation)
    cache = ConversationRuntimeCache(rejecting_factory, close, clock=lambda: now,
                                     idle_lifetime=timedelta(seconds=1))
    async with cache.lease(PRINCIPAL, "idle") as idle:
        pass
    now += timedelta(seconds=2)
    with pytest.raises(RuntimeError, match="factory rejected"):
        async with cache.lease(PRINCIPAL, "reject"):
            pass
    assert idle.closed
    await cache.aclose()


@pytest.mark.asyncio
async def test_cancelled_rejection_keeps_expiry_cleanup_visible_to_shutdown():
    """Detached cleanup survives cancellation and is included in shutdown drain."""
    now = datetime(2026, 10, 10, tzinfo=UTC)
    closing, release = asyncio.Event(), asyncio.Event()
    async def delayed_close(runtime):
        """Hold detached idle cleanup until the test permits release.

        Args:
            runtime: Controlled conversation resource to close.
        """
        if runtime.conversation == "idle":
            closing.set()
            await release.wait()
        runtime.closed = True
    cache = ConversationRuntimeCache(build, delayed_close, clock=lambda: now,
                                     idle_lifetime=timedelta(seconds=1))
    async with cache.lease(PRINCIPAL, "idle") as idle:
        pass
    async with cache.lease(PRINCIPAL, "held"):
        await cache.invalidate(PRINCIPAL, "held")
        now += timedelta(seconds=2)
        async def rejected():
            """Attempt admission for held, invalidated state."""
            async with cache.lease(PRINCIPAL, "held"):
                pass
        task = asyncio.create_task(rejected())
        await closing.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    shutdown = asyncio.create_task(cache.aclose())
    await asyncio.sleep(0)
    assert not shutdown.done() and not idle.closed
    release.set()
    await shutdown
    assert idle.closed

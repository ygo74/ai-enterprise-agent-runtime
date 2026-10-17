"""Typed retry and service-scoped circuit-breaker policies."""

from __future__ import annotations

import asyncio
import math
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetrySettings:
    """Bound retry attempts and exponential backoff for one outbound operation.

    Args:
        max_attempts (int): Total operation attempts, including the first call.
        initial_delay_seconds (float): Initial exponential-backoff multiplier.
        maximum_delay_seconds (float): Upper bound for one backoff delay.
    """

    max_attempts: int = 3
    initial_delay_seconds: float = 0.1
    maximum_delay_seconds: float = 0.5

    def __post_init__(self) -> None:
        """Reject unbounded or internally inconsistent retry settings."""
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("retry.max_attempts must be between 1 and 10")
        if not math.isfinite(self.initial_delay_seconds) or self.initial_delay_seconds <= 0:
            raise ValueError("retry.initial_delay_seconds must be positive")
        if (
            not math.isfinite(self.maximum_delay_seconds)
            or self.maximum_delay_seconds < self.initial_delay_seconds
        ):
            raise ValueError(
                "retry.maximum_delay_seconds must be finite and greater than or equal to the initial delay"
            )


@dataclass(frozen=True, slots=True)
class CircuitBreakerSettings:
    """Configure when a service circuit opens and how long it remains open.

    Args:
        failure_threshold (int): Consecutive failed operations before opening.
        open_seconds (float): Cooldown before one half-open probe is permitted.
    """

    failure_threshold: int = 5
    open_seconds: float = 30.0

    def __post_init__(self) -> None:
        """Reject circuit settings that cannot make progress or bound waiting."""
        if self.failure_threshold < 1:
            raise ValueError("circuit_breaker.failure_threshold must be at least 1")
        if not math.isfinite(self.open_seconds) or self.open_seconds <= 0:
            raise ValueError("circuit_breaker.open_seconds must be finite and positive")


class CircuitState(StrEnum):
    """The three states of a service circuit."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when a service call is rejected by an open circuit."""

    def __init__(self) -> None:
        """Create a caller-safe failure that contains no service or request data."""
        super().__init__("remote service circuit is open")


class ServiceCircuitBreaker:
    """Track consecutive availability failures for one upstream service.

    A short thread lock protects state transitions used by synchronous and
    asynchronous callers. It is never held while a network request runs.

    Args:
        settings (CircuitBreakerSettings): Threshold and cooldown for the service.
    """

    def __init__(self, settings: CircuitBreakerSettings) -> None:
        """Initialize a closed circuit with no recorded failures."""
        self._settings = settings
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False

    @property
    def state(self) -> CircuitState:
        """Return the effective state, including an elapsed open interval."""
        with self._lock:
            if (
                self._state is CircuitState.OPEN
                and self._opened_at is not None
                and time.monotonic() - self._opened_at >= self._settings.open_seconds
            ):
                return CircuitState.HALF_OPEN
            return self._state

    def before_call(self) -> None:
        """Reserve the single half-open probe or reject this service call.

        Raises:
            CircuitOpenError: Another recovery probe is in flight or cooldown remains.
        """
        with self._lock:
            if self._state is CircuitState.CLOSED:
                return
            if self._state is CircuitState.OPEN:
                if (
                    self._opened_at is None
                    or time.monotonic() - self._opened_at < self._settings.open_seconds
                ):
                    raise CircuitOpenError()
                self._state = CircuitState.HALF_OPEN
                self._probe_in_flight = False
            if self._probe_in_flight:
                raise CircuitOpenError()
            self._probe_in_flight = True

    def record_success(self) -> None:
        """Close the circuit after a successful operation or probe."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._opened_at = None
            self._probe_in_flight = False

    def record_failure(self) -> None:
        """Advance the failure count and open or reopen the circuit as needed."""
        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._open()
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._settings.failure_threshold:
                self._open()

    def _open(self) -> None:
        """Start a fresh cooldown while the state lock is held."""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._probe_in_flight = False


class ServiceCircuitBreakerRegistry:
    """Share one breaker state for each stable upstream service identity.

    Args:
        default_settings (CircuitBreakerSettings): Settings used when a service
            has no explicit override.
    """

    def __init__(
        self, default_settings: CircuitBreakerSettings | None = None
    ) -> None:
        """Initialize the registry and its concurrency-safe service map."""
        self._default_settings = default_settings or CircuitBreakerSettings()
        self._lock = threading.Lock()
        self._breakers: dict[str, ServiceCircuitBreaker] = {}
        self._settings: dict[str, CircuitBreakerSettings] = {}

    def for_service(
        self,
        service_identity: str,
        settings: CircuitBreakerSettings | None = None,
    ) -> ServiceCircuitBreaker:
        """Return the shared breaker for one service, rejecting policy conflicts.

        Args:
            service_identity (str): Stable endpoint identity, never caller identity.
            settings (CircuitBreakerSettings | None): Optional service override.

        Raises:
            ValueError: The identity is empty or callers configured conflicting
                policies for the same service.
        """
        identity = service_identity.strip()
        if not identity:
            raise ValueError("service identity must not be empty")
        selected = settings or self._default_settings
        with self._lock:
            existing = self._breakers.get(identity)
            if existing is not None:
                if self._settings[identity] != selected:
                    raise ValueError(
                        "conflicting circuit breaker settings for one upstream service"
                    )
                return existing
            breaker = ServiceCircuitBreaker(selected)
            self._breakers[identity] = breaker
            self._settings[identity] = selected
            return breaker


class RetryExecutor:
    """Run explicitly classified sync or async operations with bounded retries."""

    @staticmethod
    def run_sync(
        operation: Callable[[float], T],
        *,
        settings: RetrySettings,
        timeout_seconds: float,
        retryable_exceptions: tuple[type[Exception], ...],
    ) -> T:
        """Run a synchronous operation, passing its remaining total deadline.

        Args:
            operation (Callable[[float], T]): Operation receiving remaining seconds.
            settings (RetrySettings): Attempt and backoff bounds.
            timeout_seconds (float): Total elapsed-time limit for all attempts.
            retryable_exceptions (tuple[type[Exception], ...]): Only these failures retry.
        """
        if timeout_seconds <= 0:
            raise ValueError("retry deadline must be positive")
        retrying, _ = RetryExecutor._retrying_types()
        deadline = time.monotonic() + timeout_seconds
        for attempt in retrying(
            stop=RetryExecutor._stop(settings, timeout_seconds),
            wait=RetryExecutor._wait(settings),
            retry=RetryExecutor._retry_if(retryable_exceptions),
            reraise=True,
        ):
            with attempt:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("outbound operation deadline exceeded")
                return operation(remaining)
        raise TimeoutError("outbound operation deadline exceeded")

    @staticmethod
    async def run_async(
        operation: Callable[[float], Awaitable[T]],
        *,
        settings: RetrySettings,
        timeout_seconds: float,
        retryable_exceptions: tuple[type[Exception], ...],
    ) -> T:
        """Run an asynchronous operation within one deadline and retry budget.

        Args:
            operation (Callable[[float], Awaitable[T]]): Async operation receiving remaining seconds.
            settings (RetrySettings): Attempt and backoff bounds.
            timeout_seconds (float): Total elapsed-time limit for attempts and waits.
            retryable_exceptions (tuple[type[Exception], ...]): Only these failures retry.
        """
        if timeout_seconds <= 0:
            raise ValueError("retry deadline must be positive")
        _, async_retrying = RetryExecutor._retrying_types()
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        async with asyncio.timeout(timeout_seconds):
            async for attempt in async_retrying(
                stop=RetryExecutor._stop(settings, timeout_seconds),
                wait=RetryExecutor._wait(settings),
                retry=RetryExecutor._retry_if(retryable_exceptions),
                reraise=True,
            ):
                with attempt:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise TimeoutError("outbound operation deadline exceeded")
                    return await operation(remaining)
        raise TimeoutError("outbound operation deadline exceeded")

    @staticmethod
    def _retrying_types() -> tuple[Any, Any]:
        """Load Tenacity lazily so base security imports stay dependency-light."""
        try:
            from tenacity import AsyncRetrying, Retrying
        except ImportError as error:
            raise RuntimeError(
                "bounded HTTP retries require the optional Tenacity dependency"
            ) from error
        return Retrying, AsyncRetrying

    @staticmethod
    def _stop(settings: RetrySettings, timeout_seconds: float) -> Any:
        """Build the combined finite-attempt and elapsed-time stop condition."""
        from tenacity import stop_after_attempt, stop_after_delay

        return stop_after_attempt(settings.max_attempts) | stop_after_delay(
            timeout_seconds
        )

    @staticmethod
    def _wait(settings: RetrySettings) -> Any:
        """Build bounded exponential backoff with randomized jitter."""
        from tenacity import wait_random_exponential

        return wait_random_exponential(
            multiplier=settings.initial_delay_seconds,
            max=settings.maximum_delay_seconds,
        )

    @staticmethod
    def _retry_if(exceptions: tuple[type[Exception], ...]) -> Any:
        """Build a retry predicate for the explicitly eligible exception types."""
        from tenacity import retry_if_exception_type

        return retry_if_exception_type(exceptions)


DEFAULT_CIRCUIT_BREAKERS = ServiceCircuitBreakerRegistry()

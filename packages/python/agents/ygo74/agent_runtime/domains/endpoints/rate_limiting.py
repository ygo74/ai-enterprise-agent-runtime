"""Optional SlowAPI integration for manifest-selected FastAPI routes."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar, cast

from pydantic import SecretStr
from ygo74.agent_runtime.domains.http.asgi_lifecycle import AsgiShutdownRegistrar

EndpointT = TypeVar("EndpointT", bound=Callable[..., Any])
_RATE_LIMIT = re.compile(r"^[1-9][0-9]*/(?:second|minute|hour|day|month|year)$")


@dataclass(frozen=True, slots=True)
class RateLimitSettings:
    """Resolved SlowAPI settings applied to each enabled invocation endpoint.

    Args:
        limits: SlowAPI limit expressions applied independently to each route.
        storage_uri: Optional backend URI, redacted from the settings representation.
    """

    limits: tuple[str, ...]
    storage_uri: SecretStr | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Reject invalid direct host settings instead of silently omitting a quota."""
        if not self.limits:
            raise ValueError("rate limits must contain at least one limit")
        if any(_RATE_LIMIT.fullmatch(limit) is None for limit in self.limits):
            raise ValueError("rate limits must use '<positive integer>/<period>' syntax")
        if len(set(self.limits)) != len(self.limits):
            raise ValueError("rate limits must not contain duplicates")


class SlowApiRateLimiter:
    """Set up one SlowAPI limiter and decorate only the agent's enabled routes.

    SlowAPI is imported inside this adapter so importing configuration contracts
    or using FastAPI without a rate-limit declaration does not require it.

    Args:
        application: FastAPI app whose lifespan owns the limiter backend.
        settings: Validated per-client quota and optional backend URI.
    """

    def __init__(self, application: Any, settings: RateLimitSettings) -> None:
        """Create the limiter, install its 429 handler, and register backend cleanup."""
        try:
            from slowapi import Limiter
            from slowapi.errors import RateLimitExceeded
            from slowapi.util import get_remote_address
        except ImportError as error:
            raise RuntimeError(
                "rate limiting requires the optional agents HTTP dependencies; install ygo74-agent-runtime-agents[http]"
            ) from error

        limiter_options: dict[str, Any] = {
            "key_func": get_remote_address,
            "storage_uri": (
                settings.storage_uri.get_secret_value()
                if settings.storage_uri is not None
                else "memory://"
            ),
        }
        try:
            self._limiter = Limiter(**limiter_options)
        except Exception:  # noqa: BLE001 - Backend errors may contain a credential-bearing URI.
            raise ValueError(
                "http.rate_limit.storage_uri could not initialize its backend"
            ) from None
        application.state.limiter = self._limiter
        application.add_exception_handler(
            RateLimitExceeded, self._handle_rate_limit_exceeded
        )
        self._settings = settings
        storage = getattr(self._limiter, "_storage", None)
        close = getattr(storage, "close", None)
        if not callable(close):
            backend_client = getattr(storage, "storage", None)
            close = getattr(backend_client, "close", None)
        if callable(close):
            AsgiShutdownRegistrar.register(
                application, close, wrap_lifespan=True
            )

    def decorate(self, endpoint: EndpointT) -> EndpointT:
        """Apply every configured per-route limit to an endpoint with a Request argument.

        Args:
            endpoint: FastAPI endpoint function whose first request context supplies the client IP.
        """
        decorated: Callable[..., Any] = endpoint
        for limit in reversed(self._settings.limits):
            decorated = self._limiter.limit(limit)(decorated)
        return cast(EndpointT, decorated)

    def register(self, application: Any, path: str, endpoint: EndpointT) -> None:
        """Register one enabled route after applying all configured limits.

        Args:
            application: FastAPI app receiving the invocation route.
            path: Existing runtime invocation path.
            endpoint: Route handler that accepts a FastAPI Request argument.
        """
        application.post(path)(self.decorate(endpoint))

    @staticmethod
    async def _handle_rate_limit_exceeded(request: Any, error: Any) -> Any:
        """Return the runtime's stable 429 error without echoing request data.

        Args:
            request: Request associated with the rejected invocation.
            error: SlowAPI rate-limit exception; its detail is intentionally not exposed.
        """
        _ = (request, error)
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded"},
        )

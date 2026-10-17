"""Attach synchronous resource cleanup to an ASGI application's shutdown."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any


class AsgiShutdownRegistrar:
    """Register a synchronous cleanup callback across ASGI lifecycle APIs."""

    @staticmethod
    def register(application: Any, callback: Callable[[], None]) -> None:
        """Run ``callback`` when the application's router begins shutdown.

        Older Starlette routers expose shutdown-event registration. Newer
        routers expose only a lifespan context, so this method wraps that
        context while preserving its yielded application state.

        Args:
            application (Any): FastAPI or Starlette application to extend.
            callback (Callable[[], None]): Synchronous cleanup owned by the runtime.

        Raises:
            TypeError: The application has no supported router lifecycle interface.
        """
        router = getattr(application, "router", None)
        if router is None:
            raise TypeError("ASGI application does not expose a router")

        add_event_handler = getattr(router, "add_event_handler", None)
        if callable(add_event_handler):
            add_event_handler("shutdown", callback)
            return

        original_lifespan = getattr(router, "lifespan_context", None)
        if not callable(original_lifespan):
            raise TypeError("ASGI router does not expose a shutdown lifecycle")

        @asynccontextmanager
        async def lifespan_context(app: Any) -> Any:
            """Preserve the existing lifespan and run cleanup on context exit."""
            async with original_lifespan(app) as state:
                try:
                    yield state
                finally:
                    callback()

        router.lifespan_context = lifespan_context

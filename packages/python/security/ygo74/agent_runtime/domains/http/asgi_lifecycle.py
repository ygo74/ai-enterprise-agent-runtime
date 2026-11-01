"""Attach synchronous resource initialization and cleanup to an ASGI lifespan."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any


class AsgiShutdownRegistrar:
    """Register synchronous resource callbacks across ASGI lifecycle APIs."""

    @staticmethod
    def register(
        application: Any,
        callback: Callable[[], None],
        *,
        startup: Callable[[], None] | None = None,
        wrap_lifespan: bool = False,
    ) -> None:
        """Register cleanup and optional initialization for application resources.

        Older Starlette routers expose shutdown-event registration. Newer
        routers expose only a lifespan context, so this method wraps that
        context while preserving its yielded application state. When startup is
        supplied or ``wrap_lifespan`` is true, wrapping the lifespan keeps
        resources alive until application scopes have closed, even when the
        router also exposes shutdown events. This is required for apps whose
        custom lifespan replaces the router's registered shutdown handlers.

        Args:
            application (Any): FastAPI or Starlette application to extend.
            callback (Callable[[], None]): Synchronous cleanup owned by the runtime.
            startup (Callable[[], None] | None): Optional resource initialization
                before entering the application's lifespan. Cleanup runs after it exits.
            wrap_lifespan (bool): Wrap the existing lifespan instead of using a
                shutdown event, including when the router exposes event handlers.

        Raises:
            TypeError: The application has no supported router lifecycle interface.
        """
        router = getattr(application, "router", None)
        if router is None:
            raise TypeError("ASGI application does not expose a router")

        add_event_handler = getattr(router, "add_event_handler", None)
        if startup is None and not wrap_lifespan and callable(add_event_handler):
            add_event_handler("shutdown", callback)
            return

        original_lifespan = getattr(router, "lifespan_context", None)
        if not callable(original_lifespan):
            raise TypeError("ASGI router does not expose a shutdown lifecycle")

        @asynccontextmanager
        async def lifespan_context(app: Any) -> Any:
            """Preserve the existing lifespan and run cleanup on context exit."""
            try:
                if startup is not None:
                    startup()
                async with original_lifespan(app) as state:
                    yield state
            finally:
                callback()

        router.lifespan_context = lifespan_context

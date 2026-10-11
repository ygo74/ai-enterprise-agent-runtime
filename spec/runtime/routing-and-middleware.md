# Routing and middleware

## Purpose

An application may host more than one agent or use case behind one endpoint.
Routing maps an internal route key to the handler that owns the behavior. The
route key is separate from a public model ID: clients discover the ID, while
application configuration selects the route.

The runtime also provides middleware as an explicit way to inspect or change a
request and response around handler execution. These are composition building
blocks. Endpoint adapters do not silently install middleware or infer routes
from application code.

## Route selection and dispatch

`RouteRegistry` stores handlers under unique keys. Registering a duplicate key
fails, and resolving an unknown key is an error. A dispatcher resolves the
request's route key and invokes the handler with a normalized exchange request.
The handler result is validated at the exchange boundary.

In the Python HTTP adapter, an explicit internal route key takes precedence. If
none is present, a known public model ID can resolve through the descriptor
registry; otherwise the configured default route is used. This fallback does
not make the public model ID an authorization decision. Access policy is
checked separately.

## Middleware behavior

Middleware receives a context with the request and the response available so
far, plus a continuation for the next middleware or final handler. It may inspect
or replace values before continuing, inspect or replace the returned response,
or short-circuit without calling the continuation. Middleware order is
deterministic: Python uses the supplied sequence; the cross-language registries
sort registered items by their numeric order.

The application chooses which middleware to register and where to call the
pipeline. Python FastAPI endpoint registration accepts handlers and dispatchers,
not a middleware collection. The application composes middleware in its
dispatcher or handler path. Middleware is therefore not an automatic
authentication or authorization layer; endpoint security must be configured
separately.

## Language scope and acceptance

Routing and middleware building blocks exist in Python, .NET, and Java, but
HTTP host integration is language-specific. The current runtime does not ship
built-in ASP.NET Core or Spring route registration.

- Duplicate route keys and unknown route lookups fail visibly.
- Route resolution selects one handler before dispatch.
- Middleware executes in a stable order and can short-circuit or modify the
  request/response around the handler.
- Applications must explicitly compose the pipeline and separately configure
  endpoint authentication and authorization.

See the [pipeline and state specification](pipelines-and-state.md),
[`test_dispatch_routing.py`](../../tests/integration/python/test_dispatch_routing.py),
and [`test_middleware_pipeline.py`](../../tests/integration/python/test_middleware_pipeline.py).

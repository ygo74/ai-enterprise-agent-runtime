# Pipelines and state

## Routing and dispatch

`RouteRegistry` maps an internal route key to a handler for a standard exchange
request. Duplicate registrations fail, and resolving an unknown key raises a
routing error. The `Dispatcher` boundary separates route resolution from
handler invocation. In the Python FastAPI adapter, an explicit route key takes
precedence; otherwise a registered public model ID resolves through its agent
descriptor, then the configured default route is used.

The public agent/model ID and internal route key are separate values. The ID is
stable client-facing catalog data; the route key selects application behavior.
See the [agent catalog](../discovery/agent-catalog.md) for discovery and model
resolution.

## Middleware

Middleware wraps handler execution with a context containing the request and an
optional response. Each middleware can inspect or replace the request, call the
next handler, then inspect or replace its response. The Python pipeline nests
middleware in the supplied order and uses an explicit continuation; a middleware
can short-circuit by returning without calling it. Registries in Python, .NET,
and Java order middleware by a numeric order value.

The Python FastAPI adapter does not accept a middleware collection directly.
Applications compose the pipeline in their handler or dispatcher. The endpoint
adapter handles transport mapping and authentication before calling the
configured entrypoint.

## Conversation contracts and cache

Python provides a `ConversationEngine` protocol and turn/reply values as a
framework-neutral boundary. `ConversationRuntimeCache` is an optional
process-local building block for keeping an application runtime per authenticated
subject and conversation ID. It builds each entry once under concurrent access,
leases entries while a request uses them, closes expired or evicted idle
runtimes, bounds idle state by a maximum size, and exposes explicit release and
shutdown operations. Defaults are a 30-minute idle lifetime and 200
conversations. When every entry is leased, the cache can temporarily exceed the
configured size rather than closing a runtime that is in use.

The cache does not define a transport-level conversation protocol or persist
state across process restarts. The application supplies the runtime factory and
closer, chooses how request IDs map to conversations, and owns durable or shared
storage when multi-process state is required. An authenticated principal is
required to partition cached conversations safely.

## Language limits

Routing, dispatch, and middleware building blocks exist across Python, .NET,
and Java. Conversation contracts and the runtime cache are currently Python
only. Middleware is not automatically installed by the provider endpoint
adapters. See [language support](../compatibility/language-status.md).

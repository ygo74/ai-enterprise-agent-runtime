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

## Conversation contracts, HTTP turns, and cache

Python provides the framework-neutral `ConversationTurn`, `AgentReply`, and
`ConversationEngine` contracts. These values keep request identity, conversation
identity, message text, reply text, and pending-confirmation identifiers
independent of a particular agent framework.

`AgentConversation[RuntimeT, SessionT]` is a typed container for the application
runtime, framework session, pending-confirmation store, confirmation runner,
conversation ID, and pending-action renderer. Its structural ports describe
only what the shared HTTP flow needs; an application can use its own typed
runtime and framework session without inheriting from a runtime base class.
`HttpConversationEngine` leases the container from `ConversationRuntimeCache`,
recognizes confirmation commands before invoking the model, runs a claimed
confirmation through the application-supplied runner, and returns an
`AgentReply` that includes the remaining pending actions. This consolidates
repeated HTTP conversation plumbing while leaving framework state and
application composition local.

`ConversationRuntimeCache` is an optional process-local building block for
keeping an application runtime per authenticated subject and conversation ID. It
builds each entry once under concurrent access, leases entries while a request
uses them, closes expired or evicted idle runtimes, bounds idle state by a
maximum size, and exposes explicit release and shutdown operations. Defaults
are a 30-minute idle lifetime and 200 conversations. When every entry is
leased, the cache can temporarily exceed the configured size rather than
closing a runtime that is in use.

These APIs do not define a transport-level conversation protocol, persist state
across process restarts, or select how application request IDs map to
conversations. The application supplies the runtime and session factories and
closers, confirmation store and runner, and any durable or shared storage needed
for multi-process state. An authenticated principal must partition cached
conversations safely. The engine and cache are Python-only.

## Language limits

Routing, dispatch, and middleware building blocks exist across Python, .NET,
and Java. Conversation contracts and the runtime cache are currently Python
only. Middleware is not automatically installed by the provider endpoint
adapters. See [language support](../compatibility/language-status.md).

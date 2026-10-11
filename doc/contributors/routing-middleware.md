# Routing and middleware

## Routing

`RouteRegistry` stores handlers by route key. `Dispatcher` resolves the key,
validates the handler outcome, and runs the selected handler through the
middleware pipeline. Missing keys and invalid outcomes use typed domain errors
and are mapped at the endpoint boundary.

```mermaid
classDiagram
    class RouteRegistry
    class Dispatcher
    class UseCaseHandler
    class MiddlewarePipeline
    class ResponseValidator
    Dispatcher --> RouteRegistry : resolves route
    Dispatcher --> MiddlewarePipeline : executes chain
    MiddlewarePipeline --> UseCaseHandler : invokes
    Dispatcher --> ResponseValidator : checks result
```

Routes are explicit configuration. Do not infer a route from model text or
silently substitute a default handler after an unknown explicit route.

## Middleware order

Middleware wraps a continuation. Registration order determines nesting and
therefore request/response order. A middleware may inspect or replace a context,
call the next item, or short-circuit. Middleware errors are mapped to the
standard error contract by the dispatcher or endpoint layer.

```mermaid
sequenceDiagram
    participant D as Dispatcher
    participant M1 as Middleware 1
    participant M2 as Middleware 2
    participant H as Handler
    D->>M1: execute(context)
    M1->>M2: call next(context)
    M2->>H: call next(context)
    H-->>M2: result
    M2-->>M1: post-process result
    M1-->>D: final result
```

The Python APIs are under [`routing`](../../packages/python/agents/ygo74/agent_runtime/routing/)
and [`middleware`](../../packages/python/agents/ygo74/agent_runtime/middleware/).
Equivalent implementations are under the .NET and Java package roots.

Tests: [dispatch routing](../../tests/integration/python/test_dispatch_routing.py),
[middleware pipeline](../../tests/integration/python/test_middleware_pipeline.py),
and [middleware short-circuit](../../tests/integration/python/test_middleware_short_circuit.py).

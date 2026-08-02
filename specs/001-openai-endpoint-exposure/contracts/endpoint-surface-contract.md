# Endpoint Surface Contract (Feature 001)

## Scope

This contract defines the externally exposed endpoint behavior for the first
feature release.

## Supported Endpoint Types

- OpenAI-compatible Chat Completions
- OpenAI-compatible Responses
- Anthropic-compatible Messages

## Contract Requirements

- Incoming endpoint payloads MUST be normalized to `StandardExchangeRequest`.
- Developer handlers MUST receive only normalized exchange requests.
- Handler outputs MUST be expressed as `StandardExchangeResponse` and mapped back
  to endpoint-compatible response payloads.
- Streaming mode MUST be supported for all supported endpoint types and mapped
  through `StandardStreamingExchangeEvent` semantics.
- Error responses MUST use the standardized `ErrorEnvelope` categories.

## Routing Contract

- Each request MUST resolve a `routeKey`.
- A registered handler MUST exist for each active routeKey.
- Missing handler registration MUST yield a structured routing error.
- Stream requests MUST route to the same handler registration model as non-stream requests.

## Middleware Pipeline Contract

- Middleware components MUST execute in deterministic order before handler invocation.
- Each middleware MUST receive message context plus a next-callback to invoke the next middleware.
- Middleware MAY short-circuit processing and return a structured response without invoking downstream middleware or handler.
- After handler completion, middleware post-processing MUST execute in reverse chain order.
- Middleware failures MUST be mapped to the standardized error envelope categories.

## Authentication Contract

- Runtime supports JWT authentication and API-key + user-resolution hook.
- On success, runtime MUST provide `authContext` to handlers.
- On failure, runtime MUST return authentication error without handler execution.

## Authorization Contract

- Authorization is developer-owned in handler logic.
- Authorization denial MUST return a structured authorization error and MUST NOT
  execute protected use case logic.

## Configuration Contract

- Endpoint and auth settings MUST be configurable through native mechanisms of
  each host framework (language-specific options/config/DI patterns).
- Invalid configuration MUST fail fast with actionable configuration errors.

## Namespace Contract

- Library namespace root MUST be `ygo74` across language artifacts.
- Python package root MUST start with `ygo74`.
- .NET namespace root MUST start with `Ygo74`.
- Java group/package root MUST start with `ygo74`.

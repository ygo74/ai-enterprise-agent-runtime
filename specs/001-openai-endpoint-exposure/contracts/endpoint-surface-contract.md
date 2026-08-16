# Endpoint Surface Contract (Feature 001)

## Scope

This contract defines the externally exposed endpoint behavior for the first
feature release.

## Supported Endpoint Types

- OpenAI-compatible Chat Completions
- OpenAI-compatible Responses
- Anthropic-compatible Messages
- OpenAI-compatible model listing and single-model retrieval
- Anthropic-compatible model listing and single-model retrieval
- A2A agent card served from the protocol well-known discovery location

## Discovery Route Paths

These paths are normative. All three language implementations MUST expose the
same paths so cross-language parity is observable.

|Surface|Method and path|Notes|
|---|---|---|
|Model listing (shared dialect path)|`GET /v1/models`|Dialect selected by the `anthropic-version` request header|
|Single-model retrieval (shared dialect path)|`GET /v1/models/{model_id}`|`{model_id}` is the descriptor `agentId`|
|OpenAI listing (explicit override)|`GET /openai/v1/models`|Active only when dialect split is enabled in configuration|
|OpenAI single-model (explicit override)|`GET /openai/v1/models/{model_id}`|Active only when dialect split is enabled in configuration|
|Anthropic listing (explicit override)|`GET /anthropic/v1/models`|Active only when dialect split is enabled in configuration|
|Anthropic single-model (explicit override)|`GET /anthropic/v1/models/{model_id}`|Active only when dialect split is enabled in configuration|
|A2A agent card|`GET /.well-known/agent-card.json`|Protocol well-known discovery location|

- The shared path `/v1/models` is the default. Explicit per-dialect base paths
  are opt-in through Discovery Configuration and, when enabled, the shared path
  MUST continue to serve the header-selected dialect.
- A configurable route prefix MAY be applied to the `/v1/...` paths for hosts
  that mount the runtime under a sub-path. The A2A well-known path MUST NOT be
  prefixed, because the protocol resolves it from the host root.
- Discovery Configuration MUST support an externally reachable base URL used
  when the agent card advertises endpoint locations, so values remain correct
  when the runtime is deployed behind a reverse proxy.

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

## Discovery Contract

- A single `AgentDescriptor` per exposed agent MUST be the only source of agent
  identity and capability metadata for every discovery surface.
- Each descriptor MUST bind to exactly one `routeKey`, and duplicate public agent
  identifiers MUST fail initialization.
- Agents registered without an explicit descriptor MUST receive a derived minimal
  descriptor so no exposed agent is silently undiscoverable.
- Model listings MUST return one entry per discoverable agent, ordered by
  ascending `agentId` using case-sensitive Unicode code-point comparison. This
  ordering is the only defined ordering and MUST be identical in Python, .NET,
  and Java, including when the catalogue changes between requests.
- An empty catalogue MUST return a successful response containing an empty entry
  collection in the requested dialect envelope, never an error.
- Model identifier matching MUST be exact and case-sensitive. Leading and
  trailing whitespace in the requested identifier MUST be rejected as a
  structured not-found error rather than trimmed.
- Model identifiers returned by discovery MUST be accepted verbatim as the model
  field of Chat Completions, Responses, and Anthropic Messages requests and MUST
  route to the advertised agent.
- When both dialects share the model listing path, dialect selection MUST use the
  Anthropic protocol version header, defaulting to the OpenAI dialect when the
  header is absent, and MUST be overridable through configuration.
- Anthropic-compatible listings MUST honor Anthropic pagination parameters and
  return correct continuation indicators.
- Descriptor attributes without a native provider field MUST be exposed through a
  documented additive extension section only.
- The A2A agent card MUST be projected from the same descriptor and MUST report
  identical values for every attribute shared with the provider model entries.
- The agent card MUST advertise enforced authentication schemes without exposing
  secret material.
- Declared capability claims MUST be validated at initialization against actual
  endpoint configuration and MUST fail fast on contradiction.
- Each discovery surface MUST be independently enablable, and disabled surfaces
  MUST return a structured not-found error.
- Agents marked hidden MUST be absent from listings while remaining invocable.
- Discovery MUST support public or authenticated access modes and MUST support a
  developer-owned per-caller visibility filter.
- Entries a caller may not see MUST be indistinguishable from non-existent agents.
- A visibility filter that raises, or that exceeds its configured evaluation
  deadline, MUST fail closed: the affected descriptor is treated as not visible,
  the failure is logged with the descriptor identifier and the failure cause, and
  no listing is served from an unevaluated catalogue.
- Discovery failures MUST use the standardized `ErrorEnvelope` categories.

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

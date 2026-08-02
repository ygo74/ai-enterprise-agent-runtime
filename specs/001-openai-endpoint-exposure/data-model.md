# Data Model: OpenAI-Compatible Endpoint Exposure

## Entity: EndpointExposureConfiguration

- Description: Configuration that enables endpoint surfaces and runtime behavior for a use case.
- Fields:

  - `useCaseRouteKey` (string, required, non-empty)
  - `enableChatCompletions` (boolean, default false)
  - `enableResponses` (boolean, default false)
  - `enableAnthropicMessages` (boolean, default false)
  - `enableStreaming` (boolean, default false)
  - `authMode` (enum: `jwt`, `api_key`, `optional`)
  - `jwtConfig` (object, required when `authMode=jwt`)
  - `apiKeyConfig` (object, required when `authMode=api_key`)
  - `userResolutionHookRef` (string, required when `authMode=api_key`)
  - `exchangeVersion` (string, default `v1`)
  - `streamExchangeVersion` (string, default `v1`)
- Validation rules:

  - At least one endpoint surface must be enabled.
  - Route key must be unique per service host.
  - `jwtConfig` and `apiKeyConfig` are mutually exclusive unless explicitly supported by host policy.
  - `enableStreaming=true` requires stream-capable endpoint surface(s) enabled.

## Entity: HandlerRegistration

- Description: Links a route key to a developer handler implementation.
- Fields:

  - `useCaseRouteKey` (string, required)
  - `handlerRef` (string/object reference, required)
  - `inputContractVersion` (string, required, currently `v1`)
  - `outputContractVersion` (string, required, currently `v1`)
- Validation rules:

  - One active handler per route key.
  - Handler contract versions must match runtime-supported exchange versions.

## Entity: MiddlewareRegistration

- Description: Ordered metadata that defines middleware chain composition for a route or global scope.
- Fields:

  - `middlewareId` (string, required)
  - `scope` (enum: `global`, `route`, required)
  - `routeKey` (string, required when `scope=route`)
  - `order` (integer, required)
  - `middlewareRef` (string/object reference, required)
  - `canShortCircuit` (boolean, default true)
- Validation rules:

  - Order values must be unique per scope and route.
  - Middleware chain must be deterministic and stable across runs.

## Entity: StandardExchangeRequest

- Description: Canonical request delivered to developer handler.
- Fields:

  - `requestId` (string, required)
  - `timestampUtc` (datetime, required)
  - `endpointType` (enum: `openai.chat_completions`, `openai.responses`, `anthropic.messages`)
  - `routeKey` (string, required)
  - `model` (string, optional)
  - `input` (object/array/string, required)
  - `stream` (boolean, default false)
  - `streamRequestOptions` (object, optional)
  - `metadata` (object, optional)
  - `authContext` (AuthenticatedUserContext, optional/required by auth mode)
- Validation rules:

  - `endpointType` must be one of supported values.
  - `input` must be present and schema-valid for the selected endpoint mapping.

## Entity: StandardExchangeResponse

- Description: Canonical response returned by developer handler.
- Fields:

  - `requestId` (string, required)
  - `status` (enum: `success`, `error`, required)
  - `output` (object/array/string, required when `status=success`)
  - `error` (ErrorEnvelope, required when `status=error`)
  - `metadata` (object, optional)
- Validation rules:

  - Exactly one of `output` or `error` must be set.
  - `requestId` must match inbound request for correlation.

## Entity: StandardStreamingExchangeEvent

- Description: Canonical stream event emitted by runtime mapping layer from developer handler streaming output.
- Fields:

  - `requestId` (string, required)
  - `sequence` (integer, required, monotonic)
  - `eventType` (enum: `chunk`, `completion`, `error`, required)
  - `delta` (object/string, required when `eventType=chunk`)
  - `finalOutput` (object/array/string, optional, used at completion)
  - `error` (ErrorEnvelope, required when `eventType=error`)
  - `timestampUtc` (datetime, required)
- Validation rules:

  - Sequence must be strictly increasing per request stream.
  - Exactly one of `delta`, `finalOutput`, or `error` applies based on `eventType`.

## Entity: MessagePipelineContext

- Description: Per-request mutable context passed through middleware chain and handler.
- Fields:

  - `request` (StandardExchangeRequest, required)
  - `response` (StandardExchangeResponse, optional until resolved)
  - `streamEvents` (array of StandardStreamingExchangeEvent, optional)
  - `middlewareTrace` (array of middleware execution records, optional)
  - `shortCircuited` (boolean, default false)
  - `items` (object/map for extensions, optional)
- Validation rules:

  - `request` is immutable for identity/correlation fields (`requestId`, `routeKey`).
  - Middleware modifications must preserve contract validity.
  - `shortCircuited=true` implies handler execution is skipped.

## Entity: AuthenticatedUserContext

- Description: Normalized identity context projected by runtime authentication.
- Fields:

  - `userId` (string, required)
  - `authType` (enum: `jwt`, `api_key`, required)
  - `claims` (object/map, optional)
  - `scopes` (array of string, optional)
  - `tenantId` (string, optional)
  - `rawPrincipalRef` (string/object reference, optional)
- Validation rules:

  - `userId` must be present after successful authentication.
  - For `api_key`, context must come from user-resolution hook output.

## Entity: ErrorEnvelope

- Description: Structured error payload for all failure categories.
- Fields:

  - `code` (string, required)
  - `category` (enum: `validation`, `authentication`, `authorization`, `routing`, `mapping`, `handler_execution`, `configuration`)
  - `message` (string, required)
  - `details` (object/array, optional)
  - `requestId` (string, optional)
  - `retryable` (boolean, optional)
- Validation rules:

  - `code` and `category` must be stable and documented.
  - `message` must be safe for API response contexts.

## Entity: LibraryNamespaceIdentity

- Description: Namespace root identity applied across language artifacts.
- Fields:

  - `namespaceRoot` (string, required, fixed to `ygo74`)
  - `pythonPackageRoot` (string, required, starts with `ygo74`)
  - `dotnetNamespaceRoot` (string, required, starts with `Ygo74`)
  - `javaGroupRoot` (string, required, starts with `ygo74`)
- Validation rules:

  - Namespace root must remain consistent for all released artifacts.

## Relationships

- EndpointExposureConfiguration 1..* -> HandlerRegistration (by route key)
- EndpointExposureConfiguration 0..* -> MiddlewareRegistration (global/route scope)
- StandardExchangeRequest 1..1 -> AuthenticatedUserContext (when authenticated)
- StandardExchangeResponse 0..1 -> ErrorEnvelope (if error)
- StandardExchangeRequest 0..* -> StandardStreamingExchangeEvent (when `stream=true`)
- MessagePipelineContext 1..1 -> StandardExchangeRequest
- MessagePipelineContext 0..1 -> StandardExchangeResponse

## State Transitions

- Request lifecycle:

  - `received` -> `normalized` -> `authenticated` -> `middleware_pre` -> `dispatched` -> `handled` -> `middleware_post` -> `mapped` -> `responded`
  - `received` -> `normalized` -> `authenticated` -> `middleware_pre` -> `dispatched` -> `handled` -> `middleware_post` -> `streaming` -> `stream_completed`
  - `received` -> `normalized` -> `authenticated` -> `middleware_pre` -> `short_circuited` -> `responded`
- Failure states:

  - `received` -> `rejected_validation`
  - `normalized` -> `rejected_authentication`
  - `authenticated` -> `rejected_authorization` (developer logic)
  - `dispatched` -> `failed_routing`
  - `middleware_pre` -> `failed_middleware`
  - `middleware_post` -> `failed_middleware`
  - `handled` -> `failed_handler_execution`
  - `mapped` -> `failed_mapping`
  - `streaming` -> `failed_stream`

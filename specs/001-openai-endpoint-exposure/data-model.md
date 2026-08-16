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

## Entity: AgentDescriptor

- Description: Canonical provider-neutral record describing one exposed agent. Sole source of truth for every discovery projection.
- Fields:

  - `agentId` (string, required, unique, non-empty) - public identifier advertised as the model identifier
  - `routeKey` (string, required) - dispatch route this descriptor is bound to
  - `displayName` (string, required)
  - `description` (string, required)
  - `version` (string, required, semantic version recommended)
  - `owner` (string, required, default derived from host configuration)
  - `createdAtUtc` (datetime, required)
  - `documentationUrl` (string, optional)
  - `tags` (array of string, optional)
  - `capabilities` (AgentCapabilitySet, required)
  - `skills` (array of AgentSkill, optional, default empty)
  - `securitySchemes` (array of string, optional) - names of authentication schemes the runtime enforces
  - `discoveryVisibility` (enum: `listed`, `hidden`, default `listed`)
  - `metadata` (object/map, optional) - free-form, carried through without runtime interpretation
- Validation rules:

  - `agentId` must be unique across the runtime instance and must be safe for use in a request path segment and in a `model` request field.
  - `routeKey` must resolve to a registered handler at initialization.
  - `capabilities` must not contradict the effective `EndpointExposureConfiguration` for `routeKey`.
  - Missing optional fields receive documented defaults; a registered handler with no declared descriptor receives a minimal derived descriptor built from its `routeKey`.
  - `securitySchemes` must reference schemes the runtime actually enforces and must never contain secret material.
  - Descriptors are immutable after initialization.

## Entity: AgentCapabilitySet

- Description: Declared behavioral characteristics of an agent, used for discovery output and for initialization-time consistency validation.
- Fields:

  - `streaming` (boolean, default false)
  - `inputModalities` (array of string, default `["text"]`)
  - `outputModalities` (array of string, default `["text"]`)
  - `toolInvocation` (boolean, default false)
  - `structuredOutput` (boolean, default false)
  - `maxInputSize` (integer, optional) - maximum accepted input size
  - `maxOutputSize` (integer, optional) - maximum produced output size
  - `extensions` (object/map, optional) - additional capability facts projected into the provider extension section
- Validation rules:

  - `streaming=true` requires streaming to be enabled for the bound route's endpoint surfaces.
  - Modality arrays must be non-empty.
  - Size limits, when present, must be positive.

## Entity: AgentSkill

- Description: Named, described unit of agent competence, surfaced in the agent card and in provider extension sections.
- Fields:

  - `skillId` (string, required, unique within the descriptor)
  - `name` (string, required)
  - `description` (string, required)
  - `tags` (array of string, optional)
  - `examples` (array of string, optional)
  - `inputModalities` (array of string, optional, defaults to descriptor capabilities)
  - `outputModalities` (array of string, optional, defaults to descriptor capabilities)
- Validation rules:

  - `skillId` must be unique within its descriptor.
  - Skill modalities must be a subset of the descriptor capability modalities.

## Entity: DescriptorRegistry

- Description: Initialization-time collection of all agent descriptors, responsible for uniqueness, defaulting, route binding, and stable ordering.
- Fields:

  - `descriptors` (map of `agentId` -> AgentDescriptor, required)
  - `ordering` (enum: `agent_id_ascending`, default `agent_id_ascending`)
- Validation rules:

  - Duplicate `agentId` values fail initialization with an actionable error naming the duplicate.
  - Every descriptor must resolve to a registered handler route key.
  - Lookup by `agentId` must be exact-match and O(1).
  - Listing order must be deterministic and identical across language implementations.

## Entity: DiscoveryConfiguration

- Description: Settings controlling which discovery surfaces are exposed and how they behave.
- Fields:

  - `enableOpenAiModels` (boolean, default false)
  - `enableAnthropicModels` (boolean, default false)
  - `enableAgentCard` (boolean, default false)
  - `dialectSelection` (enum: `header`, `openai_only`, `anthropic_only`, default `header`)
  - `requireAuthentication` (boolean, default false)
  - `visibilityRuleRef` (string/object reference, optional)
  - `defaultPageSize` (integer, default 20)
  - `maxPageSize` (integer, default 100)
- Validation rules:

  - A disabled surface must return a structured not-found response, not a partially served payload.
  - `dialectSelection=header` selects the Anthropic dialect when the Anthropic protocol version header is present and the OpenAI dialect otherwise.
  - `defaultPageSize` must not exceed `maxPageSize`; both must be positive.
  - `requireAuthentication=true` requires an auth mode to be configured on the runtime.

## Entity: DiscoveryVisibilityRule

- Description: Developer-owned extension point deciding which descriptors a given authenticated caller may see.
- Fields:

  - `ruleRef` (string/object reference, required)
  - `appliesTo` (enum: `listing`, `retrieval`, `both`, default `both`)
- Validation rules:

  - Rule receives the `AuthenticatedUserContext` and the candidate descriptor and returns a visibility decision.
  - A denied descriptor must produce a response indistinguishable from a non-existent agent.
  - Rule failures must map to a structured error envelope and must not disclose descriptor content.

## Entity: DiscoveryProjection

- Description: Dialect-specific, stateless, read-only rendering of an AgentDescriptor into a target wire shape.
- Variants and source mapping:

  - `openai.model` - identifier from `agentId`, object type constant, creation timestamp from `createdAtUtc`, ownership from `owner`; all non-native attributes emitted inside a single additive extension object.
  - `anthropic.model` - entry type constant, identifier from `agentId`, display name from `displayName`, creation timestamp from `createdAtUtc`; all non-native attributes emitted inside a single additive extension object; listings carry the Anthropic list envelope and pagination indicators.
  - `a2a.agent_card` - name from `displayName`, description, version, provider from `owner`, documentation reference, capability flags from `capabilities`, default input/output modalities, skill collection from `skills`, security schemes from `securitySchemes`.
- Validation rules:

  - Projections must be pure functions of the descriptor with no independent state or configuration.
  - For every attribute shared by two or more projections, all projections must emit the same value.
  - No projection may emit credential or secret material.

## Relationships

- EndpointExposureConfiguration 1..* -> HandlerRegistration (by route key)
- EndpointExposureConfiguration 0..* -> MiddlewareRegistration (global/route scope)
- StandardExchangeRequest 1..1 -> AuthenticatedUserContext (when authenticated)
- StandardExchangeResponse 0..1 -> ErrorEnvelope (if error)
- StandardExchangeRequest 0..* -> StandardStreamingExchangeEvent (when `stream=true`)
- MessagePipelineContext 1..1 -> StandardExchangeRequest
- MessagePipelineContext 0..1 -> StandardExchangeResponse
- HandlerRegistration 1..1 -> AgentDescriptor (by route key; derived minimal descriptor when none is declared)
- DescriptorRegistry 1..* -> AgentDescriptor (keyed by `agentId`)
- AgentDescriptor 1..1 -> AgentCapabilitySet
- AgentDescriptor 0..* -> AgentSkill
- AgentDescriptor 1..3 -> DiscoveryProjection (openai.model, anthropic.model, a2a.agent_card)
- DiscoveryConfiguration 0..1 -> DiscoveryVisibilityRule
- DiscoveryVisibilityRule 1..1 -> AuthenticatedUserContext (evaluated per caller)
- StandardExchangeRequest.model 1..1 -> AgentDescriptor.agentId (discovery-to-invocation round trip)

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
- Descriptor lifecycle:

  - `declared` -> `defaulted` -> `route_bound` -> `capability_validated` -> `registered` -> `immutable`
  - `declared` -> `rejected_duplicate_identifier`
  - `defaulted` -> `rejected_unresolved_route_key`
  - `route_bound` -> `rejected_capability_contradiction`
- Discovery request lifecycle:

  - `received` -> `surface_enabled` -> `authenticated` -> `visibility_filtered` -> `dialect_selected` -> `projected` -> `responded`
  - `received` -> `rejected_surface_disabled`
  - `surface_enabled` -> `rejected_authentication`
  - `authenticated` -> `rejected_unsupported_version`
  - `authenticated` -> `rejected_invalid_pagination`
  - `visibility_filtered` -> `responded_not_found` (denied and non-existent agents are indistinguishable)

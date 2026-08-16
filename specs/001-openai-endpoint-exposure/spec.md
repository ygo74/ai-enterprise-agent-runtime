# Feature Specification: OpenAI and Anthropic Endpoint Exposure

**Feature Branch**: `[001-openai-endpoint-exposure]`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "les librairies dotnet/java/python doivent permettrent aux developpeurs d'agents d'exposer leur AI use case dans les deux formats les plus courants qui sont les endpoints openai (chat/completion ou responses) et les endpoints anthropic messages. Les developpeurs doivent pouvoir simplement ajouter ces endpoints en utilisant les methodes standards de configuration de ces framework. je ne veux pas modifier les templates des specifications plan et tasks avec cette demande mais je veux developper cette premiere fonctionnalite. Je veux donc l'ajouter sous forme de premiere specification qui consiste a l'exposition des endpoints compatibles openai et qui permettra aux developpeurs de recuperer les payload pour les traiter comme ils le souhaitent dans leur use case. Il faudrait aussi un format d'echange standard pour qu'ils puissent implementer son use case et fournir le resultat"

**Additional input** (2026-08-16): User description: "dans les specs pour les endpoints compatibles openai/anthropic, j'ai oublie de demander celui qui permet d'exposer la liste des modeles. Par exemple, il faudrait pour openai un endpoint v1/models qui renvoit comme nom de modele le nom de l'agent et d'autres informations qui permettent de connaitre les capacites de l'agent. Pour anthropic je ne sais pas s'il y a une correspondance. Si oui il faudrait alors aussi un endpoint pour recuperer le nom de l'agent et ses capacites. Si les deux providers ont d'autres informations a retourner il faut aussi les mettre. Ces informations doivent etre configurables et comme il faudra aussi exposer le protocole a2a avec la card de l'agent je pense que ce serait bien d'utiliser la meme source pour l'agent card et ce qui sera retourne par le endpoint v1/models et celui d'anthropic"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Expose OpenAI and Anthropic Compatible Endpoints (Priority: P1)

As an agent library integrator, I can enable OpenAI-compatible and Anthropic-compatible endpoint exposure for my use case so I can receive normalized request payloads and return results through standard endpoint contracts.

**Why this priority**: This is the core value of the feature and the minimum capability needed for standalone agent integration.

**Independent Test**: Can be fully tested by enabling endpoint exposure for one use case, sending valid Chat Completions, Responses, and Anthropic Messages requests, and confirming the library emits a normalized handler payload and returns a valid formatted response.

**Acceptance Scenarios**:

1. **Given** endpoint exposure is enabled for a use case, **When** a valid OpenAI Chat Completions request is received, **Then** the library provides the developer with a normalized payload and returns a compliant response envelope.
2. **Given** endpoint exposure is enabled for a use case, **When** a valid OpenAI Responses request is received, **Then** the library provides the developer with a normalized payload and returns a compliant response envelope.
3. **Given** endpoint exposure is enabled for a use case, **When** a valid Anthropic Messages request is received, **Then** the library provides the developer with a normalized payload and returns a compliant response envelope.

---

### User Story 1b - Stream Responses Across Endpoint Families (Priority: P1)

As an integrator, I can enable streaming mode for OpenAI and Anthropic endpoints so clients can consume partial outputs progressively.

**Why this priority**: Streaming is a first-class behavior expected by client applications and must be consistently available in all supported endpoint families.

**Independent Test**: Can be tested by enabling streaming mode and validating incremental chunks/events are emitted for Chat Completions, Responses, and Anthropic Messages.

**Acceptance Scenarios**:

1. **Given** streaming is enabled, **When** a valid OpenAI Chat Completions request with streaming mode is sent, **Then** the endpoint returns a compliant stream sequence until completion.
2. **Given** streaming is enabled, **When** a valid OpenAI Responses request with streaming mode is sent, **Then** the endpoint returns a compliant stream sequence until completion.
3. **Given** streaming is enabled, **When** a valid Anthropic Messages request with streaming mode is sent, **Then** the endpoint returns a compliant stream sequence until completion.

---

### User Story 2 - Configure With Native Framework Patterns (Priority: P2)

As a developer using Python, .NET, or Java, I can activate and configure endpoint exposure using the standard configuration methods of my framework so integration remains simple and idiomatic.

**Why this priority**: Adoption depends on simple configuration without custom bootstrapping.

**Independent Test**: Can be tested independently by configuring endpoint exposure in each language runtime using native configuration approaches and verifying the endpoint becomes available without additional custom startup code.

**Acceptance Scenarios**:

1. **Given** a library consumer uses the framework-standard configuration path, **When** they provide endpoint settings, **Then** endpoint exposure is activated without requiring non-standard bootstrap steps.
2. **Given** configuration is invalid or incomplete, **When** startup or initialization occurs, **Then** the library reports clear validation errors and does not expose partially configured endpoints.

---

### User Story 3 - Implement Use Case Logic Through Standard Exchange Format (Priority: P3)

As a use case developer, I can process a standardized request payload and return a standardized result payload so my business logic is decoupled from endpoint wire details.

**Why this priority**: A stable exchange format ensures portability and consistency across clients and languages.

**Independent Test**: Can be tested by implementing one use case handler against the standard exchange format and validating successful processing and response generation for both supported OpenAI-compatible endpoint types.

**Acceptance Scenarios**:

1. **Given** a request arrives from a supported endpoint, **When** the library maps it to the standard exchange request format, **Then** the handler receives the same logical fields regardless of endpoint type.
2. **Given** the handler returns a standard exchange response, **When** the library maps it back to endpoint format, **Then** clients receive a valid endpoint-specific response payload.

---

### User Story 4 - Route Payloads to Developer Handlers Through a Decoupled Pipeline (Priority: P1)

As a developer, I can register my own processing handlers and let the library route incoming payloads to them through a decoupled dispatch pipeline so endpoint plumbing and business logic remain cleanly separated.

**Why this priority**: Clean routing and decoupling are key to maintainability and extensibility across Python, .NET, and Java.

**Independent Test**: Can be tested by registering at least two handlers for different use cases, sending requests to each endpoint, and verifying each payload is dispatched to the correct handler without endpoint-specific logic in handler code.

**Acceptance Scenarios**:

1. **Given** multiple handlers are registered, **When** a request targets a specific use case, **Then** the dispatch pipeline routes the standardized payload to the matching handler.
2. **Given** a handler is not registered for a routed use case, **When** a request is received, **Then** the system returns a structured not-implemented or not-registered error.

---

### User Story 4b - Inspect and Modify Messages Through Middleware Chain (Priority: P1)

As a developer, I can register middleware components that inspect or modify messages before and after handler execution so I can implement cross-cutting behaviors in a reusable pipeline.

**Why this priority**: Middleware chaining is a core extensibility pattern for observability, validation, enrichment, and policy enforcement without coupling business handlers to infrastructure concerns.

**Independent Test**: Can be tested by registering multiple middleware components with defined order, verifying each one receives the message context, calls the next middleware, and can observe/transform both request and response phases.

**Acceptance Scenarios**:

1. **Given** multiple middlewares are registered with explicit order, **When** a request is processed, **Then** each middleware is invoked in order before the handler and can pass control to the next middleware.
2. **Given** middleware post-processing is enabled, **When** the handler returns, **Then** middleware executes in reverse chain for post-handler processing and can inspect/adjust response context.
3. **Given** a middleware short-circuits the chain, **When** policy conditions are met, **Then** the handler is not executed and a structured response is returned.

---

### User Story 5 - Authentication Context and Developer-Owned Authorization (Priority: P1)

As a developer, I receive an authenticated user context from the runtime and I can implement my own authorization logic so I keep full control over domain-specific access rules.

**Why this priority**: The platform must centralize common authentication while preserving developer control over authorization decisions.

**Independent Test**: Can be tested by invoking a handler with (a) a valid JWT and (b) a valid API key resolved through a user hook, then confirming the handler receives user context and can enforce custom authorization decisions.

**Acceptance Scenarios**:

1. **Given** a valid JWT is supplied, **When** the request enters the pipeline, **Then** the system authenticates it and provides user context to the handler input.
2. **Given** API key mode is configured, **When** a request includes a valid API key, **Then** the runtime invokes the configured user-resolution hook and provides resolved user context to the handler.
3. **Given** authentication succeeds but authorization fails in developer logic, **When** the handler evaluates access, **Then** the system returns a structured forbidden response without executing protected business logic.

---

### User Story 6 - Declare Agent Identity and Capabilities From a Single Source (Priority: P2)

As an agent developer, I declare the identity, description, and capabilities of each exposed agent one single time in configuration so every discovery surface reports the same facts without me maintaining duplicate metadata.

**Why this priority**: The shared descriptor is the prerequisite for provider-compatible model discovery and for the future A2A agent card. Without one canonical source, each discovery surface would drift and duplicate configuration.

**Independent Test**: Can be tested by declaring one agent descriptor, reading it back through the runtime descriptor registry, and confirming every declared attribute is preserved, defaulted, and validated before any discovery endpoint is exposed.

**Acceptance Scenarios**:

1. **Given** an agent descriptor is declared with identity, description, version, and capability attributes, **When** the runtime initializes, **Then** the descriptor is registered against its route key and is retrievable as a single canonical record.
2. **Given** two agents are declared with the same public agent identifier, **When** the runtime initializes, **Then** initialization fails with an actionable configuration error naming the duplicated identifier.
3. **Given** an agent descriptor omits optional capability attributes, **When** the runtime initializes, **Then** documented defaults are applied and the descriptor remains valid.
4. **Given** a handler is registered with no declared descriptor, **When** the runtime initializes, **Then** a minimal descriptor is derived from the route key so the agent remains discoverable.
5. **Given** a descriptor claims a capability that contradicts the runtime endpoint configuration, **When** the runtime initializes, **Then** initialization fails with an actionable error identifying the contradiction.

---

### User Story 6b - Discover Agents Through Provider-Compatible Model Endpoints (Priority: P2)

As a client application built against the OpenAI or Anthropic API, I call the provider model listing endpoint and receive each exposed agent as a selectable model entry, so I can populate a model picker and then invoke the agent through the already-supported endpoints without custom integration code.

**Why this priority**: Provider-compatible clients routinely list models before letting a user select a target. Without discovery, the exposed agents are invisible to those clients even though invocation already works.

**Independent Test**: Can be tested by declaring two agents, calling the model listing endpoint in each provider dialect, and confirming both agents appear with identifiers that are accepted verbatim in a subsequent invocation request.

**Acceptance Scenarios**:

1. **Given** two agents are exposed, **When** a client requests the OpenAI-compatible model list, **Then** the response uses the OpenAI list envelope with one model entry per discoverable agent.
2. **Given** an agent is exposed, **When** a client requests the OpenAI-compatible model list, **Then** the returned model identifier is accepted verbatim as the model field of a subsequent Chat Completions, Responses, or Anthropic Messages request routed to that same agent.
3. **Given** two agents are exposed, **When** a client requests the model list in Anthropic dialect, **Then** the response uses the Anthropic list envelope with one entry per discoverable agent, each carrying an identifier, a display name, and a creation timestamp.
4. **Given** the same runtime serves both dialects on the shared model listing path, **When** a request carries the Anthropic protocol version header, **Then** the Anthropic dialect is returned; **and when** it does not, **Then** the OpenAI dialect is returned.
5. **Given** more agents are exposed than the requested page size, **When** a client requests the Anthropic model list with pagination parameters, **Then** the requested page and correct continuation indicators are returned.
6. **Given** an agent is exposed, **When** a client requests that single model by identifier in either dialect, **Then** only that agent's entry is returned in the matching dialect shape.
7. **Given** an unknown model identifier is requested, **When** the client calls the single-model endpoint, **Then** a structured not-found error is returned using the standard error envelope.
8. **Given** an agent declares capability attributes with no native provider field, **When** the model entry is produced, **Then** those attributes are exposed through a documented additive extension section that provider clients can safely ignore.

---

### User Story 6c - Serve an A2A-Ready Agent Card From the Same Descriptor (Priority: P3)

As an agent consumer using the Agent-to-Agent protocol, I retrieve the agent card from the runtime well-known discovery location and find the same name, description, version, capabilities, and skills that the provider model endpoints report, so discovery is trustworthy regardless of which protocol I speak.

**Why this priority**: The agent card is why the descriptor must stay provider-neutral. Delivering it alongside the model endpoints proves the shared source works for a richer metadata model and prevents the descriptor from being over-fitted to the OpenAI shape.

**Independent Test**: Can be tested by declaring one descriptor with skills and capabilities, retrieving the agent card, and asserting field-by-field equivalence with the provider model entries for every shared attribute.

**Acceptance Scenarios**:

1. **Given** an agent descriptor is declared, **When** a consumer retrieves the agent card from the well-known discovery location, **Then** the card reports the same name, description, version, and capability facts as the provider model entries.
2. **Given** the descriptor declares skills with names, descriptions, and examples, **When** the agent card is produced, **Then** each declared skill is present in the card skill collection.
3. **Given** the descriptor declares streaming support, **When** the agent card is produced, **Then** the card streaming capability flag matches the runtime streaming configuration for that agent.
4. **Given** the descriptor declares the authentication schemes the runtime enforces, **When** the agent card is produced, **Then** the card advertises those schemes without disclosing any secret material.
5. **Given** the agent card surface is disabled in configuration, **When** a consumer retrieves the well-known discovery location, **Then** a structured not-found error is returned and the provider model endpoints remain unaffected.

---

### User Story 6d - Control Discovery Access and Visibility (Priority: P3)

As a platform owner, I control who can enumerate exposed agents and which agents each caller sees, so discovery does not leak the existence of agents a caller is not entitled to use.

**Why this priority**: Discovery is an information-disclosure surface in a runtime that already authenticates every invocation, but it is a hardening concern rather than the core discovery capability.

**Independent Test**: Can be tested by enabling authentication on discovery, calling the listing anonymously and as an authenticated caller, and confirming the anonymous call is rejected while the authenticated call returns only permitted entries.

**Acceptance Scenarios**:

1. **Given** discovery requires authentication, **When** an unauthenticated caller requests the model list, **Then** a structured authentication error is returned and no agent metadata is disclosed.
2. **Given** a developer-owned discovery visibility rule is configured, **When** an authenticated caller requests the model list, **Then** only the entries permitted for that caller are returned.
3. **Given** a caller is not permitted to see a given agent, **When** the caller requests that agent by identifier, **Then** the response is indistinguishable from the response for a non-existent agent.
4. **Given** an agent is marked hidden from discovery, **When** a client lists models, **Then** the agent is absent from the listing while remaining directly invocable by its identifier.
5. **Given** discovery is configured as publicly readable, **When** an unauthenticated caller requests the model list, **Then** the listing is returned without requiring credentials.

### Edge Cases

- What happens when a request targets an unsupported endpoint variant or version?
- How does the system behave when required fields are missing or malformed in incoming payloads?
- How does the system handle use case handler timeouts or handler exceptions?
- What happens when a handler returns output that cannot be converted to the selected endpoint response format?
- How does the system behave when Chat Completions, Responses, and Anthropic Messages are enabled but only one is configured correctly?
- How does the system behave when no handler is registered for the routed use case?
- How does the system behave when JWT authentication succeeds but required user attributes are missing for authorization decisions?
- How does the system behave when API key user-resolution hook returns no user or a malformed user context?
- How does the system behave when a streaming connection is interrupted mid-response?
- How does the system behave when streaming mode is requested but disabled for the target endpoint family?
- How does the system behave when a middleware fails before calling the next middleware?
- How does the system behave when middleware modifies the message into an invalid state for downstream processing?
- How does the system behave when middleware intentionally short-circuits and returns early?
- How does the system behave when the shared model listing path receives a request carrying no provider dialect indicator?
- What happens when a caller requests a model identifier that differs only by letter case or surrounding whitespace from a registered agent identifier?
- What happens when an agent identifier contains characters that are legal in configuration but ambiguous or unsafe in a request path?
- How does the system behave when no agent is exposed at all - is an empty listing returned or an error?
- How does the system behave when pagination parameters are out of range, contradictory, or reference an entry that no longer exists?
- What happens when a descriptor declares a capability the runtime has no way to verify?
- What happens when declared skills or metadata make the discovery payload unreasonably large?
- How does the system behave when discovery is requested while agent registration is still in progress?
- How does the system behave when a descriptor attribute is meaningful for one discovery surface but has no equivalent in another?
- How does the system behave when a developer-supplied discovery visibility rule raises an error or times out?
- What happens when the agent card advertises endpoint locations that differ from where the runtime is actually reachable behind a proxy?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow agent library consumers to expose use cases through OpenAI-compatible Chat Completions endpoints.
- **FR-002**: System MUST allow agent library consumers to expose use cases through OpenAI-compatible Responses endpoints.
- **FR-002b**: System MUST allow agent library consumers to expose use cases through Anthropic-compatible Messages endpoints.
- **FR-003**: System MUST provide developers with the request payload in a standardized exchange request format before use case logic executes.
- **FR-004**: System MUST allow developers to provide use case results in a standardized exchange response format that is mapped back to the originating endpoint contract.
- **FR-005**: System MUST validate endpoint configuration at initialization time and report actionable validation errors.
- **FR-006**: System MUST support endpoint configuration through framework-standard configuration mechanisms for Python, .NET, and Java.
- **FR-007**: System MUST provide consistent error categories and error payload structure across supported language implementations.
- **FR-008**: System MUST preserve endpoint metadata needed by developers to make use-case decisions (for example request identifier, model identifier, and user-provided context fields when present).
- **FR-009**: System MUST support deterministic mapping rules between endpoint payloads and the standard exchange format, including behavior for missing optional fields.
- **FR-010**: System MUST produce equivalent functional behavior across Python, .NET, and Java implementations for the same request/response scenarios.
- **FR-011**: System MUST provide a decoupled dispatch model that routes standardized incoming payloads to developer-implemented handlers based on use case routing metadata.
- **FR-012**: System MUST keep endpoint transport/mapping concerns separated from developer business logic concerns so handlers process standardized payload objects only.
- **FR-013**: System MUST provide a common authentication layer that supports JWT-based authentication and yields authenticated user context to handlers.
- **FR-014**: System MUST provide an API key mode where user context is resolved through a developer-provided hook before handler execution.
- **FR-015**: System MUST leave authorization decisions to developer-implemented logic and MUST expose authenticated user context needed for those decisions.
- **FR-016**: System MUST return consistent structured error responses for authentication failures, authorization failures, and handler registration/routing failures.
- **FR-017**: System MUST support streaming mode for OpenAI-compatible Chat Completions, OpenAI-compatible Responses, and Anthropic-compatible Messages endpoints.
- **FR-018**: System MUST expose a standardized streaming exchange event contract so developer handlers can emit partial outputs and completion/failure signals consistently.
- **FR-019**: System MUST package libraries under the `ygo74` namespace root in Python, .NET, and Java artifacts.
- **FR-020**: System MUST provide a middleware pipeline model where each middleware receives message context and a next-callback to continue processing.
- **FR-021**: System MUST support middleware execution before handler invocation and after handler completion.
- **FR-022**: System MUST support deterministic middleware ordering and documented short-circuit behavior.
- **FR-023**: System MUST provide structured error handling for middleware failures using the same error envelope model.
- **FR-024**: System MUST provide a single provider-neutral agent descriptor as the sole source of truth for all agent identity and capability metadata exposed by any discovery surface.
- **FR-025**: System MUST allow developers to declare, for each exposed agent, at minimum a public agent identifier, a display name, a description, a version, an owner or provider label, and a creation timestamp.
- **FR-026**: System MUST allow developers to declare agent capability attributes covering at least streaming support, supported input modalities, supported output modalities, tool or function invocation support, structured output support, maximum accepted input size, and maximum produced output size. Size attributes MUST carry an explicit unit selected from tokens, characters, or bytes, defaulting to tokens, and the unit MUST be reported on every discovery surface that exposes a size value.
- **FR-027**: System MUST allow developers to declare zero or more named agent skills, each with an identifier, a name, a description, optional tags, and optional usage examples, plus arbitrary additional descriptor metadata carried through to discovery surfaces without runtime interpretation.
- **FR-028**: System MUST apply documented defaults for every optional descriptor attribute, MUST derive a minimal valid descriptor for any registered agent that has no declared descriptor, MUST bind each descriptor to exactly one route key, and MUST reject duplicate public agent identifiers at initialization.
- **FR-029**: System MUST expose an OpenAI-compatible model listing endpoint returning one model entry per discoverable agent, and an OpenAI-compatible single-model retrieval endpoint, with entry fields populated from descriptor attributes. Both endpoints MUST be served from the normative paths declared in the endpoint surface contract.
- **FR-030**: System MUST expose an Anthropic-compatible model listing endpoint using the Anthropic list envelope with its pagination parameters and continuation indicators, and an Anthropic-compatible single-model retrieval endpoint, with entry fields populated from descriptor attributes. Both endpoints MUST be served from the normative paths declared in the endpoint surface contract.
- **FR-031**: System MUST deterministically select the provider dialect when both providers publish discovery on the same path, using the Anthropic protocol version header as the dialect indicator, defaulting to the OpenAI dialect when absent, and MUST allow this selection to be overridden through configuration.
- **FR-032**: System MUST guarantee that every agent identifier returned by any discovery listing is accepted verbatim as the model field of a supported invocation request and routes to the advertised agent. Identifier matching MUST be exact and case-sensitive, and an identifier differing only by letter case or by surrounding whitespace MUST NOT resolve.
- **FR-033**: System MUST expose descriptor capability attributes that have no native provider field through a documented additive extension section that does not break provider-compatible client parsing.
- **FR-034**: System MUST expose an A2A agent card projected from the same descriptor that feeds the provider model endpoints, served from the protocol well-known discovery location declared in the endpoint surface contract, populated with identity, description, version, provider, documentation reference, capability flags, default input and output modalities, and the skill collection. Endpoint locations advertised in the card MUST be derived from a configurable externally reachable base URL so the card stays correct behind a reverse proxy.
- **FR-035**: System MUST advertise, in the agent card, the authentication schemes the runtime actually enforces for that agent, without disclosing any credential or secret material.
- **FR-036**: System MUST guarantee that, for every attribute shared by two or more discovery surfaces, all surfaces report the same value derived from the descriptor.
- **FR-037**: System MUST validate at initialization that declared capability claims do not contradict the runtime endpoint configuration and that every descriptor resolves to a registered handler route key, failing fast with actionable errors.
- **FR-038**: System MUST allow each discovery surface to be enabled or disabled independently through configuration and MUST return a structured not-found response for disabled surfaces.
- **FR-039**: System MUST allow an agent to be marked as hidden from discovery listings while remaining directly invocable by its identifier.
- **FR-040**: System MUST allow discovery endpoints to be configured as publicly readable or as requiring authentication, reusing the runtime authentication layer, and MUST provide a developer-owned extension point that filters which entries a given authenticated caller may see.
- **FR-041**: System MUST return, for an agent the caller is not permitted to see, a response indistinguishable from the response for a non-existent agent.
- **FR-042**: System MUST return structured errors using the existing error envelope model for unknown identifiers, unsupported provider versions, invalid pagination parameters, authentication failures, and disabled discovery surfaces.
- **FR-043**: System MUST order discovery listings by ascending public agent identifier using case-sensitive code-point comparison, so repeated requests return entries in a stable order and the order is identical across Python, .NET, and Java.
- **FR-044**: System MUST support descriptor and discovery configuration through framework-standard configuration mechanisms for Python, .NET, and Java, and MUST produce functionally equivalent discovery output across the three implementations.
- **FR-045**: System MUST fail closed when a developer-supplied discovery visibility rule raises an error or exceeds its configured evaluation deadline: the affected agent MUST be treated as not visible to that caller, the failure MUST be logged with the agent identifier and failure cause, and no listing MUST be served from an unevaluated catalogue.
- **FR-046**: System MUST return a successful empty listing in the requested dialect envelope when no discoverable agent is exposed, and MUST NOT return an error for an empty catalogue.

### Key Entities *(include if feature involves data)*

- **Endpoint Exposure Configuration**: Defines which OpenAI-compatible and Anthropic-compatible endpoint types are enabled for a use case and the required configuration values.
- **Standard Exchange Request**: Canonical incoming payload delivered to the use case handler, independent of endpoint wire format.
- **Standard Exchange Response**: Canonical outgoing payload produced by the use case handler, independent of endpoint wire format.
- **Standard Streaming Exchange Event**: Canonical outbound stream event emitted as partial content, completion, or error signal independent of endpoint wire format.
- **Endpoint Mapping Rules**: Declarative rules defining transformations between endpoint-specific payloads and standard exchange payloads.
- **Error Envelope**: Structured error object containing category, message, and context details returned for validation, mapping, or execution failures.
- **Handler Registration**: Mapping between a use case route key and the developer handler responsible for processing standardized requests.
- **Authenticated User Context**: Normalized security principal object produced by JWT validation or API key user-resolution hook.
- **User Resolution Hook**: Developer-supplied extension point to resolve user context from API key credentials.
- **Library Namespace Identity**: Cross-language namespace root identifier fixed to `ygo74` for package and API surface consistency.
- **Middleware Registration**: Ordered registration metadata linking middleware components to a processing pipeline.
- **Message Pipeline Context**: Mutable per-request context containing standardized request/response data and middleware state.
- **Agent Descriptor**: Canonical provider-neutral record describing one exposed agent - identity, display name, description, version, owner, creation timestamp, capability set, skills, documentation reference, discovery visibility, bound route key, and free-form additional metadata. Single source consumed by every discovery projection.
- **Agent Capability Set**: Declared behavioral characteristics of an agent - streaming support, input and output modalities, tool invocation support, structured output support, and size limits - used for discovery output and for consistency validation against runtime configuration.
- **Agent Skill**: Named, described unit of agent competence with optional tags and usage examples, surfaced through the agent card and through provider extension sections.
- **Descriptor Registry**: Initialization-time collection of all agent descriptors, responsible for uniqueness enforcement, default application, route-key binding, and stable ordering.
- **Discovery Projection**: Dialect-specific read-only view rendering an agent descriptor into a target wire shape. Three projections are in scope: OpenAI model entry, Anthropic model entry, and A2A agent card.
- **Discovery Configuration**: Settings controlling which discovery surfaces are exposed, their access requirements, the provider dialect selection rule, and pagination defaults and limits.
- **Discovery Visibility Rule**: Developer-supplied extension point deciding, per authenticated caller, which descriptors are visible in listings and retrievable individually.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of defined acceptance scenarios for Chat Completions, Responses, and Anthropic Messages pass in automated tests for each supported language implementation.
- **SC-002**: At least 95% of endpoint configuration attempts with invalid settings fail fast with actionable error messages that identify the invalid field.
- **SC-003**: For the same logical use case input, output equivalence tests across Python, .NET, and Java show no unapproved behavioral differences.
- **SC-004**: Developers can expose and validate a first use case endpoint using framework-standard configuration in under 30 minutes following project documentation.
- **SC-005**: Mapping conformance tests show 100% deterministic conversion for all mandatory fields between endpoint payloads and the standard exchange format.
- **SC-006**: Dispatch tests show 100% correct routing from standardized request payloads to registered developer handlers for declared use case routes.
- **SC-007**: Authentication tests show valid JWT and valid API key-hook flows both provide authenticated user context to handlers in all supported languages.
- **SC-008**: Authorization tests confirm developer-implemented deny decisions prevent business logic execution and return structured forbidden responses.
- **SC-009**: Streaming tests pass for OpenAI Chat Completions, OpenAI Responses, and Anthropic Messages, including completion and interrupted-stream cases.
- **SC-010**: Package and namespace validation confirms Python, .NET, and Java artifacts expose the `ygo74` namespace root consistently.
- **SC-011**: Middleware chain tests confirm deterministic invocation order, next-callback chaining, and pre/post handler interception behavior.
- **SC-012**: Middleware short-circuit tests confirm handler bypass behavior and structured responses.
- **SC-013**: Middleware error tests confirm failures are mapped to structured error envelopes consistently across language implementations.
- **SC-014**: For every declared agent, every attribute shared by two or more discovery surfaces reports an identical value across all surfaces, verified by an automated cross-surface consistency test with zero tolerated divergences.
- **SC-015**: 100% of agent identifiers returned by any discovery listing are accepted verbatim as invocation targets and route to the advertised agent, verified by an automated round-trip test.
- **SC-016**: 100% of descriptor declarations whose capability claims contradict the runtime configuration are rejected at initialization with an error message naming the contradicting attribute.
- **SC-017**: A developer can declare an agent identity and capabilities and see them correctly reflected on all three discovery surfaces in under 15 minutes using only project documentation and a single configuration block.
- **SC-018**: 100% of discovery requests from unauthenticated or unauthorized callers, when authentication is required, return a structured error and disclose no agent metadata, and 100% of agents marked hidden are absent from every listing while remaining invocable.
- **SC-019**: Repeated identical discovery listing requests return entries in an identical order in 100% of test runs, and discovery parity tests show no unapproved differences across Python, .NET, and Java for equivalent descriptor declarations.

## Assumptions

- This first feature scope targets OpenAI-compatible endpoint exposure (Chat Completions and Responses) and Anthropic-compatible Messages, including streaming mode for each.
- Transport hosting remains handled by surrounding application infrastructure.
- The runtime provides shared authentication capabilities and user-context projection, while authorization remains developer-owned.
- Developers integrate one use case at a time initially, with multiple use case exposure handled through the same contract model.
- Standard exchange format versioning starts at v1 and will evolve with backward compatibility rules defined in future specifications.
- One runtime instance may expose several agents. Each registered dispatch route key corresponds to one discoverable agent, so model listings return one entry per exposed agent rather than a single fixed entry.
- The agent name declared by the developer is what clients see as the model identifier, because model identity is the only vocabulary OpenAI-compatible and Anthropic-compatible clients understand.
- Anthropic does publish a model listing API with a list envelope, per-entry display names, and cursor-style pagination, so a genuine correspondence with the OpenAI model listing exists and both are in scope.
- Because both providers publish model listings on the same conventional path, a single route serves both dialects and the Anthropic protocol version header acts as the dialect selector, with a configuration override available for hosts that prefer separate base paths.
- Discovery scope in this feature covers the shared descriptor plus three read-only projections. Executing the A2A task protocol (task submission, state transitions, push notifications) is out of scope and is expected to be specified as a separate feature consuming the same descriptor.
- Descriptors are declared at configuration time and treated as stable for the process lifetime; dynamic runtime mutation of descriptors is out of scope for this version.
- Existing repository conventions for SOLID, DRY, and reuse-first search remain mandatory for implementation work.

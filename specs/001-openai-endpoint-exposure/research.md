# Research: OpenAI and Anthropic Endpoint Exposure

## Decision 1: Use a mediator-style dispatch pipeline in all languages

- Decision: Implement a language-specific dispatcher abstraction that receives a Standard Exchange Request and routes it to a registered developer handler by use case route key.
- Rationale: This preserves clean decoupling between endpoint transport concerns and business logic, aligns with the requested MediatR-style model in .NET, and is naturally portable to Python and Java.
- Alternatives considered:

  - Direct endpoint-to-handler wiring in each endpoint controller (rejected: creates coupling and duplicate mapping logic).
  - Reflection-based auto-dispatch without explicit registration (rejected: less explicit, harder error handling and diagnostics).

## Decision 2: Define a canonical Standard Exchange Format v1

- Decision: Introduce a language-neutral exchange envelope for inbound and outbound handler contracts.
- Rationale: A canonical payload prevents divergence across endpoint variants (OpenAI Chat Completions, OpenAI Responses, Anthropic Messages) and across language implementations.
- Alternatives considered:

  - Endpoint-native payloads passed directly to handlers (rejected: leaks transport complexity into use case logic).
  - Separate handler contracts per endpoint family (rejected: duplicates developer logic).

## Decision 3: Authentication shared by runtime, authorization owned by developer

- Decision: Runtime performs authentication and projects Authenticated User Context; developer handler performs authorization checks.
- Rationale: Common authentication removes repeated infrastructure code while preserving domain ownership for authorization rules.
- Alternatives considered:

  - Runtime-managed authorization policies (rejected: insufficient flexibility for domain-specific rules).
  - Developer-managed authentication and authorization together (rejected: duplicates auth plumbing across clients).

## Decision 4: Support two authentication modes in MVP

- Decision: Support JWT authentication and API-key authentication with a developer-provided user-resolution hook.
- Rationale: Covers common production setups while keeping authorization extensible.
- Alternatives considered:

  - JWT-only support (rejected: does not support API-key deployments).
  - API-key-only support (rejected: weak for federated identity scenarios).

## Decision 5: Keep endpoint enablement framework-native

- Decision: Endpoint exposure and auth settings are configured through standard mechanisms of each language ecosystem (native DI/options/config/environment patterns).
- Rationale: Reduces integration friction and follows user requirement for simple framework-standard setup.
- Alternatives considered:

  - Custom DSL config parser (rejected: adds cognitive overhead).
  - Code-only bootstrap APIs with no config bindings (rejected: less idiomatic in many host frameworks).

## Decision 9: Streaming is mandatory for all supported endpoint families

- Decision: Support streaming mode for OpenAI Chat Completions, OpenAI Responses, and Anthropic Messages using one standard stream-event contract.
- Rationale: Client applications commonly require progressive output and consistent streaming behavior independent of endpoint family.
- Alternatives considered:

  - Non-streaming MVP only (rejected: insufficient for real-time UX use cases).
  - Endpoint-specific stream contracts only (rejected: increases handler complexity and cross-language drift risk).

## Decision 10: Namespace root is fixed to ygo74

- Decision: Enforce `ygo74` namespace root identity across Python, .NET, and Java artifacts.
- Rationale: Provides product identity consistency and predictable package discovery.
- Alternatives considered:

  - Language-specific unrelated namespace roots (rejected: inconsistent developer experience).

## Decision 6: Standardize error envelope categories

- Decision: Define consistent error categories and envelope structure for validation, authentication, authorization, mapping, routing, and handler execution failures.
- Rationale: Cross-language parity and predictable client behavior require stable error semantics.
- Alternatives considered:

  - Language-native exception translation only (rejected: inconsistent wire behavior).

## Decision 7: Validate parity with layered test strategy

- Decision: Enforce unit tests, contract tests, endpoint integration tests, and cross-language parity tests.
- Rationale: This aligns with constitution test-first quality gates and is necessary to prevent behavioral drift.
- Alternatives considered:

  - Unit-only strategy (rejected: misses wire and cross-language divergences).

## Decision 8: Performance budget applies to runtime overhead, not business logic

- Decision: Measure and enforce runtime overhead budgets for normalization, authentication, dispatch, and mapping independently from user handler time.
- Rationale: Keeps platform accountability clear and comparable across different use case complexities.
- Alternatives considered:

  - End-to-end latency only (rejected: dominated by user logic and external dependencies).

## Decision 11: One provider-neutral AgentDescriptor is the single source of truth

- Decision: Introduce a single `AgentDescriptor` per exposed agent, declared at configuration time, from which every discovery surface is projected.
- Rationale: The OpenAI model entry, the Anthropic model entry, and the A2A agent card describe the same agent at three different fidelities. Modelling each surface separately would duplicate identity and capability metadata three times and guarantee drift. A neutral descriptor keeps the provider projections as pure functions with no independent state.
- Alternatives considered:

  - One configuration block per discovery surface (rejected: triples the configuration surface and makes drift a matter of time rather than risk).
  - Deriving the OpenAI entry as the base and extending it for the other surfaces (rejected: the OpenAI model entry is the poorest of the three shapes; anchoring on it would prevent expressing skills, modalities, and security schemes needed by the agent card).
  - Deriving descriptors purely by reflection over registered handlers (rejected: capabilities and descriptions cannot be inferred, and implicit metadata is not reviewable).

## Decision 12: Agents are advertised as models

- Decision: Each exposed agent is advertised as one model entry whose identifier is the developer-declared public agent identifier, and that identifier is the value clients place in the `model` field of an invocation request.
- Rationale: "Model" is the only selection vocabulary OpenAI-compatible and Anthropic-compatible clients understand. Mapping agent to model makes existing chat front-ends, SDKs, and gateways work unmodified.
- Alternatives considered:

  - A bespoke `/agents` catalogue endpoint only (rejected: invisible to provider-compatible clients, which is the entire point of the feature).
  - Advertising the underlying LLM model names (rejected: leaks implementation detail, breaks routing, and prevents multiple agents backed by the same model from being distinguished).

## Decision 13: Model identifier is the routing key for discovery-driven invocation

- Decision: Every identifier returned by discovery MUST be accepted verbatim as an invocation `model` value and MUST resolve to the agent that advertised it; this is enforced by an automated round-trip test.
- Rationale: Discovery that advertises a selection a client cannot then use is worse than no discovery, because clients build UI affordances on it. Binding the advertised identifier to the routing contract makes the guarantee testable rather than aspirational.
- Alternatives considered:

  - Advertising a display identifier separate from the routing key (rejected: forces clients to carry a mapping the protocols have no field for).

## Decision 14: Both provider dialects share the model listing path, selected by protocol version header

- Decision: Serve one model listing route and select the response dialect from the Anthropic protocol version header, defaulting to the OpenAI dialect when the header is absent, with a configuration override for hosts that prefer separate base paths.
- Rationale: Both providers publish model listings at the same conventional path, so a collision is unavoidable when a single runtime exposes both families. Anthropic clients always send their protocol version header, which makes it a reliable and zero-configuration discriminator. The OpenAI dialect is the safer default because OpenAI-compatible clients are the more common and the more likely to send no distinguishing header.
- Alternatives considered:

  - Distinct base path prefixes per provider (rejected as the default: many OpenAI-compatible clients hardcode the conventional base path and cannot be pointed at a prefix; retained as a configuration override for hosts that can).
  - Content negotiation on `Accept` (rejected: neither provider defines a distinguishing media type, so clients send nothing usable).
  - Returning a union payload satisfying both shapes (rejected: produces a response that is invalid for strict parsers on both sides).

## Decision 15: Non-standard capability data travels in an additive extension section

- Decision: Capability attributes with no native field in a provider's model entry are emitted inside a single documented extension object rather than as loose top-level fields.
- Rationale: Provider client libraries deserialize model entries into fixed types; unexpected top-level fields cause failures in strict parsers. A single namespaced extension object is ignorable by conforming clients and discoverable by clients that opt in.
- Alternatives considered:

  - Spreading capability fields at the top level (rejected: breaks strict provider SDK deserialization).
  - Omitting non-standard capabilities entirely from provider surfaces (rejected: the user requirement is explicitly to expose agent capabilities through these endpoints).

## Decision 16: Capability claims are validated against runtime configuration at initialization

- Decision: At initialization the runtime cross-checks descriptor claims against actual endpoint configuration and route registration, and fails fast on contradiction or on an unresolved route key.
- Rationale: This converts the descriptor from documentation into a contract. Failing at startup is far cheaper than a client discovering the lie at invocation time, and it matches the existing fail-fast configuration validation behavior of the feature.
- Alternatives considered:

  - Trusting developer declarations (rejected: silently produces a lying catalogue).
  - Deriving all capabilities automatically from configuration (rejected: descriptive attributes such as description, skills, and modalities are not derivable; automatic derivation is used only for the minimal fallback descriptor).

## Decision 17: Discovery reuses the authentication layer and the developer-owned authorization model

- Decision: Discovery endpoints are configurable as public or authenticated using the existing authentication layer, and per-caller entry filtering is exposed as a developer-owned visibility rule; entries a caller may not see are indistinguishable from non-existent agents.
- Rationale: Discovery is an information-disclosure surface, and the project already establishes that the runtime authenticates while the developer authorizes. Reusing both mechanisms avoids a second, divergent access-control model. Returning identical responses for forbidden and non-existent agents prevents enumeration of hidden agents.
- Alternatives considered:

  - Always-public discovery (rejected: leaks the agent inventory of an enterprise runtime).
  - Always-authenticated discovery (rejected: some deployments intentionally publish a public catalogue).
  - A runtime-owned role-based visibility policy (rejected: contradicts the established developer-owned authorization principle).

## Decision 18: Descriptors are immutable for the process lifetime

- Decision: Descriptors are declared at configuration time, validated once, and treated as immutable; discovery listings use a deterministic documented ordering.
- Rationale: Immutability makes discovery responses cacheable and trivially consistent across the three projections, and removes a class of concurrency questions from the first implementation. Deterministic ordering makes listing responses assertable in tests and stable for paginating clients.
- Alternatives considered:

  - Runtime-mutable descriptor registry (rejected for this version: introduces cache invalidation and pagination-stability problems for no demonstrated need).
  - Insertion-order-only listings (rejected: not reproducible across languages, which would break parity assertions).

## Reuse-First Inventory (Phase 1)

- Scope reviewed: Python runtime package roots, .NET runtime package roots, Java runtime package roots, and existing contracts under specs.
- Existing reusable implementations found: none in source package paths because this is the first runtime implementation slice.
- Reuse decision: create baseline abstractions and contract models once per language with parity-aligned shape.
- Guardrail for next phases: extend these baseline files before creating new parallel abstractions.

## Reuse-First Inventory (Discovery Amendment, 2026-08-16)

- Scope reviewed: existing route-key registration and dispatch model, authentication layer and authenticated user context, error envelope model, and the endpoint registration entry points in each language package.
- Existing reusable implementations found and reused:

  - Route-key registry: reused as the binding target for descriptors; discovery introduces no second registry of agents.
  - Authentication layer: reused unchanged for discovery access control; no discovery-specific authentication path is created.
  - Error envelope and category-to-status mapping: reused for unknown identifier, unsupported version, invalid pagination, authentication failure, and disabled surface errors.
  - Endpoint registration entry point: extended with discovery surface toggles rather than given a parallel registration API.
- New code justified: `AgentDescriptor` model, descriptor registry, and the three stateless projections. No existing abstraction expresses provider-neutral agent capability metadata, and folding it into the exchange contracts would couple invocation payloads to catalogue concerns.
- Guardrail for next phases: the three projections MUST remain pure functions over the descriptor with no independent state or configuration of their own.

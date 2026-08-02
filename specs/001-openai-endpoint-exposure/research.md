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

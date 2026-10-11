# Specification

## Issue

#16 — Refactor agent integration

## Objectif

Make the Python/FastAPI agent-hosting setup easier to read and configure through
an additive, typed composition API. Make protocol conformance explicit for
concrete implementations owned by the Python runtime.

## Contexte

The current FastAPI integration is exposed through `add_ai_endpoints`. Its
callers must pass the agent entrypoint, default route key, each enabled
invocation surface, authentication inputs, descriptor registry, and discovery
configuration together. The repository already has reusable types for agent
descriptions (`AgentDescriptor`), authentication (`AuthenticationPolicy` and
authenticator protocols), and discovery (`DiscoveryConfiguration` and
`DescriptorRegistry`). The repository guidance favors reuse and fully typed
APIs.

The issue's example is FastAPI-specific. The Python runtime currently registers
OpenAI Responses, OpenAI Chat Completions, Anthropic Messages, and the model
discovery routes it already supports. Python does not currently provide A2A or
AG-UI route adapters. The requester confirmed this issue should target
Python/FastAPI only and should simplify the surfaces already available, leaving
A2A and AG-UI out of scope.

## Problème

The current API exposes low-level runtime wiring in each application's startup
code. A developer must assemble the callable entrypoint and pass related agent,
security, and discovery data in separate arguments, which makes common setup
verbose and can make authentication intent hard to see. In addition, Python
classes that satisfy a runtime `Protocol` may do so structurally without
declaring that relationship in their base classes.

## Périmètre

- Add a Python/FastAPI hosting composition API, named `HostingFactory` unless
  implementation research finds an existing equivalent to extend.
- Let the API compose an agent entrypoint with an existing `AgentDescriptor`,
  select the currently supported invocation surfaces (OpenAI Responses, OpenAI
  Chat Completions, and Anthropic Messages), and configure authentication and
  discovery using the existing runtime configuration types.
- Keep authentication for invocation and discovery explicit and independently
  configurable. The composition API must use the configured authenticator
  chain for enabled routes and must not turn an omitted credential into a
  handler-level failure when authentication is required.
- Reuse existing endpoint, security, descriptor, and discovery behavior rather
  than adding parallel domain models or duplicating the route implementation.
- Audit concrete Python runtime classes that implement runtime `Protocol`
  contracts and declare those contracts explicitly in their class bases. This
  applies to implementations owned by this repository, not consumer-supplied
  classes or third-party implementations.
- Update the Python runtime guide and a runnable Python/FastAPI example to show
  the new composition API and its endpoint, authentication, and discovery
  configuration.
- Preserve `add_ai_endpoints` as a supported API with its current behavior.

## Hors périmètre

- Adding A2A or AG-UI routes, dependencies, adapters, or protocol contracts.
- Adding a comparable hosting factory to .NET or Java.
- Replacing the existing `AgentDescriptor`, `AuthenticationPolicy`,
  `DiscoveryConfiguration`, `DescriptorRegistry`, or `add_ai_endpoints` APIs.
- Changing provider wire formats, handler payloads, authentication semantics,
  model discovery behavior, or descriptor schemas.
- Requiring applications outside this repository to declare nominal
  inheritance from runtime protocols; structural compatibility remains valid.

## Comportement attendu

1. A Python developer can compose an agent host through one discoverable API,
   declaring the agent/descriptor, FastAPI application and enabled supported
   invocation surfaces, authentication policy, and discovery configuration.
2. The resulting FastAPI routes, route selection, request mapping, responses,
   streaming, error handling, and authentication behavior match the existing
   registration functions and configuration.
3. Discovery can be enabled independently of invocation surfaces and can have
   its own authentication requirement while using the same configured
   authenticator chain.
4. Invalid or incomplete composition is reported as an actionable setup-time
   error before the app serves requests; it does not silently expose a
   partially configured host.
5. Existing callers of `add_ai_endpoints` continue to work without changes.
6. Concrete implementations in the Python runtime that implement its
   `Protocol` contracts declare those protocols explicitly. External protocols
   already explicitly implemented by runtime classes remain explicit.

The fluent method names and the point at which routes are registered are
implementation decisions to be settled in the PLAN. The API must retain the
issue's proposed sequence of concerns: add an agent, select AI endpoint
surfaces, configure security, and configure discovery.

## Architecture concernée

- `packages/python/agents/ygo74/agent_runtime/domains/endpoints/` — FastAPI
  registration and the new composition API.
- `packages/python/agents/ygo74/agent_runtime/domains/discovery/` — existing
  descriptor registry and discovery configuration, reused unchanged unless a
  narrowly scoped adaptation is needed.
- `packages/python/security/ygo74/agent_runtime/domains/auth/` — existing
  authentication policy and authenticator protocols.
- Concrete Python implementations and their tests wherever they implement a
  protocol defined by this runtime.
- `tests/integration/python/` and Python package-level contract/type checks.
- `docs/python/agent-runtime.md` and the relevant runnable FastAPI example.

## Contraintes

- Python-only scope is an intentional framework-specific composition feature;
  it adds no language-neutral contract or agent capability and does not change
  .NET or Java behavior.
- Keep FastAPI optional and preserve the current defensive import behavior for
  consumers that install the agents distribution without the `http` extra.
- Preserve the existing ordering and semantics of authentication schemes.
  Invocation authentication and discovery authentication must each reflect the
  caller's explicit configuration.
- Do not add defaults that advertise a discovery surface or expose an
  invocation endpoint the caller did not enable.
- Protocol declarations must remain compatible with the strict Python typing
  configuration and not weaken structural compatibility for runtime consumers.
- This setup-time composition change must add no per-request processing beyond
  the existing FastAPI registration path; request behavior and performance
  remain equivalent to direct `add_ai_endpoints` registration.

## Critères d'acceptation

- An integration test configures an agent host through the new API and
  exercises every currently supported invocation surface that it enables.
- Tests confirm disabled surfaces are not registered, discovery is only
  registered when configured, and invocation and discovery authentication
  requirements are applied independently.
- Tests confirm the new API preserves current request/response mapping,
  streaming, routing, and error behavior for equivalent configuration.
- Invalid or incomplete factory configuration fails during setup with a
  clear error.
- Existing `add_ai_endpoints` integration tests pass unchanged.
- Repository-owned concrete implementations of runtime protocols declare the
  corresponding protocol in their class bases, and the configured strict type
  checks pass.
- Python documentation and a runnable example show the new API and accurately
  describe supported surfaces, security, and discovery.
- The new API adds no request-path work beyond the existing registration
  helper; equivalence is covered by behavior tests, with no new per-request
  performance budget introduced.

## Stratégie de test

- Follow the repository's test-first gate: add failing Python integration and
  protocol-conformance/type-check coverage before implementation.
- Exercise one or more supported invocation surfaces, discovery enabled and
  disabled, protected invocation, independently protected discovery, invalid
  configuration, and legacy `add_ai_endpoints` compatibility.
- Run the Python agents and security package test suites and the configured
  strict type analysis applicable to changed packages.
- Check the runnable example and documentation against the public API, then
  run `git diff --check` and review the final diff for scope.

## Risques

- A fluent API can hide the moment routes are registered or make call order
  significant. The PLAN must specify validation and registration lifecycle and
  tests must cover it.
- Authentication settings for invocation and discovery are separate today.
  Combining them carelessly could expose discovery unintentionally or let
  credential-less requests reach the agent entrypoint.
- `AuthenticationPolicy` and `add_ai_endpoints` currently expose related but
  different configuration shapes. The implementation must adapt through
  existing abstractions without changing legacy behavior.
- An explicit protocol audit can find repository-owned classes outside the
  endpoint package. Keep those changes limited to nominal declarations and
  type-correctness fixes required by the declarations.

## Questions ouvertes

- None on the feature scope. API construction syntax and route-registration
  lifecycle are design decisions for the PLAN.

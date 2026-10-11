# Implementation Plan

## Issue

#16 — Refactor agent integration

## Specification

./SPEC.md

## Objectif

Add a typed, Python/FastAPI composition API that collects one agent entrypoint
and descriptor, selected existing invocation surfaces, an explicit
authentication policy, and optional discovery configuration, then registers
them through the existing `add_ai_endpoints` implementation. Make any
repository-owned concrete implementations of runtime protocols explicit and
document the new setup.

## Préconditions

- [x] SPEC approved by the requester.
- [x] The repository is `/data/repos/ai-enterprise-agent-runtime` on `main`;
  at planning start, the approved SPEC was the only untracked change.
- [x] Reviewed the current FastAPI registration path, discovery/authentication
  configuration, relevant Python integration tests, package conventions,
  documentation, and CI validation commands.
- [x] PLAN approved by the requester.

## Étapes

### Étape 1 — Define the factory behavior through failing integration tests

**Objectif :** Lock down the new public composition flow and prove that it
produces the same routes and behavior as direct registration.

**Fichiers/composants :**

- `tests/integration/python/test_fastapi_hosting_factory.py` (new)
- Reference: `tests/integration/python/test_fastapi_add_ai_endpoints.py`
- Reference: `tests/integration/python/test_fastapi_api_key_auth.py`
- Reference: `tests/integration/python/test_discovery_round_trip.py`
- Reference: `AuthenticationPolicy`, `AgentDescriptor`, and
  `DiscoveryConfiguration`

**Modifications :**

- Write tests for the fluent sequence `HostingFactory(app)`, `add_agent`,
  `add_ai_endpoints`, `add_security`, optional `add_discovery`, and final
  `register`.
- Cover the three supported invocation surfaces individually and in
  combination, including a disabled surface returning 404.
- Verify discovery is absent unless configured, and that discovery's
  `require_authentication` setting is independent from invocation's
  `AuthenticationPolicy` requirement while using the same authenticator chain.
- Verify an API-key policy authenticates the handler context and that missing
  or invalid credentials do not invoke the agent when authentication is
  required.
- Verify missing agent/surface/security configuration, incompatible protected
  discovery with an anonymous policy, and a second call to `register` fail
  before adding partial or duplicate routes.
- Assert request mapping, routing through the descriptor's `route_key`, and
  provider response shape match direct `add_ai_endpoints` registration.

**Validation :**

- Confirm these tests fail because `HostingFactory` and its API do not yet
  exist, then keep them as the acceptance tests for implementation.

### Étape 2 — Implement the typed FastAPI hosting composition API

**Objectif :** Add the convenience API by composing existing domain objects
and route registration rather than duplicating endpoint behavior.

**Fichiers/composants :**

- `packages/python/agents/ygo74/agent_runtime/domains/endpoints/hosting_factory.py`
  (new)
- `tests/integration/python/test_fastapi_hosting_factory.py`
- Reuse without behavior change:
  `domains/endpoints/fastapi_endpoints.py::add_ai_endpoints`,
  `domains/discovery/agent_descriptor.py::AgentDescriptor`,
  `domains/discovery/descriptor_registry.py::DescriptorRegistry`,
  `domains/discovery/discovery_configuration.py::DiscoveryConfiguration`, and
  `domains/auth/authentication_policy.py::AuthenticationPolicy`

**Modifications :**

- Add an `EndpointSurface` enum for OpenAI Responses, OpenAI Chat Completions,
  and Anthropic Messages. Accept an explicit selection in
  `add_ai_endpoints`; do not add A2A or AG-UI values.
- Make `HostingFactory` hold the FastAPI app and collect exactly one
  `AgentDescriptor` plus its synchronous or asynchronous entrypoint. Derive
  the default route key and one-entry descriptor registry from that descriptor.
- Require callers to provide an `AuthenticationPolicy`; anonymous hosting must
  be deliberate through `AuthenticationPolicy.anonymous()`. Adapt the policy's
  existing authenticators and `requires_authentication` value to
  `add_ai_endpoints` without modifying that function's defaults or behavior.
- Accept optional `DiscoveryConfiguration`; pass it with the descriptor
  registry only when the caller configured discovery. Let the existing
  configuration independently control discovery routes and whether they
  require authentication.
- Provide a final `register()` operation. Validate required state and
  incompatible security configuration before mutating the FastAPI app, then
  delegate exactly once to `add_ai_endpoints`. Reject repeat configuration
  calls that would make selection ambiguous and reject repeat registration to
  prevent duplicate route installation.
- Keep FastAPI imports optional and reuse the existing runtime error when a
  caller attempts registration without the HTTP extra.
- Add full type annotations and focused docstrings for the new public API.

**Validation :**

- Run the new factory integration tests and existing targeted endpoint,
  discovery, API-key, and JWT tests.
- Compare the app's enabled route set and representative responses with the
  direct `add_ai_endpoints` path for equivalent configuration.

### Étape 3 — Make repository-owned protocol implementations explicit

**Objectif :** Meet the issue's request for explicit protocol implementation
declarations and ensure those declarations remain type-correct.

**Fichiers/composants :**

- Audit concrete Python classes in `packages/python/`,
  `tests/integration/python/`, and `docs/examples/` against runtime
  `typing.Protocol` definitions.
- Update only concrete implementations found to rely on structural conformance
  without declaring the runtime protocol in their class bases.
- Existing explicit implementations to preserve include
  `InMemoryConfirmationLedger`, `FileTokenStorage`,
  `PinnedScopeOAuthProvider`, and test doubles already inheriting their
  protocols.

**Modifications :**

- Add the corresponding protocol as an explicit base on each missing
  repository-owned implementation, importing it from its defining domain.
- Keep protocols structural for application and third-party consumers; do not
  alter protocol members, runtime checks, or consumer compatibility.
- Add or adjust focused tests/type assignments only where needed to exercise
  the newly explicit implementations.

**Validation :**

- Review the full protocol inventory and every concrete runtime implementation
  found by the audit.
- Run the Python integration tests and Ruff lint. The repository CI currently
  configures Ruff and pytest but no standalone static type checker; do not add a
  new checker or CI dependency as part of this issue.

### Étape 4 — Document the factory and update the runnable example

**Objectif :** Give Python users a runnable example of the new setup and a
clear migration path from direct endpoint registration.

**Fichiers/composants :**

- `docs/python/agent-runtime.md`
- `docs/examples/python-fastapi-quickstart/app.py` and its README, as needed
- `tests/integration/python/test_fastapi_hosting_factory.py`

**Modifications :**

- Document the exact fluent call sequence, endpoint enum values, explicit
  security policy (including deliberate anonymous hosting), optional
  discovery configuration, and final `register()` step.
- State that A2A and AG-UI are not currently available in the Python runtime
  and are not selectable through this API.
- Update the minimal FastAPI quickstart example to use the new API while
  retaining one direct `add_ai_endpoints` reference for compatibility where
  useful.
- Ensure documentation describes the supported surfaces and authentication
  semantics exactly as implemented and does not claim a cross-language
  factory.

**Validation :**

- Check imports, paths, examples, and route selection against the implementation
  and tests.
- Run the quickstart example smoke request if the environment has its declared
  Python dependencies; otherwise record the precise limitation and validate
  the example source against integration coverage.

### Étape 5 — Final validation and review

**Objectif :** Confirm Python behavior and repository hygiene before preparing
the change for review.

**Fichiers/composants :**

- All implementation, test, protocol declaration, and documentation changes
- `docs/tasks/issue-16/SPEC.md`
- `docs/tasks/issue-16/PLAN.md`

**Modifications :**

- Resolve in-scope issues found by the full Python test/lint run and review.
- Update the PLAN with delivered files, decisions, and actual validation
  results.

**Validation :**

- Run `python -m ruff check packages/python tests`.
- Run `python -m pytest tests/`.
- Check all new documentation links and example imports/commands.
- Review `git status`, the full diff, and `git diff --check` for unintended
  files, scope changes, secrets, and whitespace errors.
- Confirm there are no .NET/Java, provider contract, wire format, or A2A/AG-UI
  changes.

**État :** Implemented and reviewed. Ruff, 134 targeted integration tests,
the runnable quickstart smoke request, 494 tests outside the MCP hosting test
module, and `git diff --check` pass. The full suite remains blocked because the
first test in `test_mcp_server_hosting.py` hangs in Starlette `TestClient`
startup (`TestClient.__enter__`) under Python 3.14.3; faulthandler confirms the
stall occurs before the request reaches the app. That file is outside issue 16
and was not modified.

## Tests

- New factory integration tests for endpoint selection, route registration,
  discovery opt-in, independent authentication requirements, API-key context,
  invalid composition, duplicate registration, and legacy-equivalent behavior.
- Existing Python FastAPI endpoint, discovery, API-key, JWT, authorization,
  streaming, non-streaming, and metadata tests.
- Python runtime protocol-conformance audit and any focused test/type
  assignments needed for classes changed by that audit.
- Full CI-equivalent Python commands: Ruff over `packages/python` and `tests`,
  then pytest over `tests/`.

## Validation finale

- The factory and adjacent endpoint/authentication/discovery integration
  selection passed: 134 tests.
- Ruff passed: `/tmp/issue16-venv/bin/python -m ruff check packages/python tests`.
- The repository suite excluding
  `tests/integration/python/test_mcp_server_hosting.py` passed: 494 tests,
  including the direct-registration comparison case.
- The excluded MCP hosting module was attempted on its own and timed out on its
  first test. A faulthandler trace locates the wait in
  `starlette.testclient.TestClient.__enter__` while waiting for the AnyIO portal
  startup; no request has reached the app. This module and its implementation
  are outside issue 16 and unchanged.
- The quickstart smoke request passed for `POST /v1/responses` and
  `GET /v1/models`, including the expected echo output and descriptor ID.
- `git diff --check` passed. The change adds no request-time layer: registration
  delegates to the existing `add_ai_endpoints` helper.
- No standalone type-check command is configured in this repository's Python
  CI; type annotations and explicit protocol bases were reviewed alongside
  Ruff.

## Risques

- The factory adds stateful setup before route registration. A single explicit
  `register()` with validation before mutation avoids partial setup and
  call-order surprises.
- An anonymous authentication policy combined with discovery configured to
  require authentication would make the discovery routes unusable. Reject this
  combination during setup with a clear configuration error.
- Adding a new enum or type without package re-exports could make the API hard
  to find. Keep the public import path in the `endpoints` domain consistent
  with the existing domain-module imports and document it.
- No static type checker is configured in CI. This task will not add one;
  annotations and protocol declarations must still follow the repository's
  strict typing guidance and receive focused review.

## Décisions techniques

- Use an instance builder constructed with the FastAPI app and an explicit final
  `register()` call. The builder collects options without registering routes
  early.
- Keep one agent entrypoint/descriptor pair per factory instance. Existing
  multi-agent applications can continue to pass their dispatcher and registry
  through `add_ai_endpoints`; this issue does not add a new multi-agent
  dispatcher.
- Use an `EndpointSurface` enum rather than new booleans for the factory's
  fixed endpoint choices. The legacy function keeps its current boolean
  parameters.
- Require explicit `AuthenticationPolicy` in the new factory, including
  `AuthenticationPolicy.anonymous()` for open hosting. Keep legacy helper
  defaults unchanged.
- Treat `DiscoveryConfiguration` as optional and reuse its current independent
  discovery authentication setting.
- Do not add an A2A/AG-UI adapter, a .NET/Java equivalent, a runtime dependency,
  or a static type-checking dependency.

## Critères de réussite

- The approved composition API registers only selected existing routes and
  preserves the behavior of direct registration.
- Missing/contradictory configuration fails before the FastAPI app is mutated.
- Invocation and discovery authentication behave as explicitly configured.
- Legacy integrations and all currently supported provider surfaces remain
  unchanged.
- Repository-owned implicit protocol implementations found in scope become
  explicit; structural consumer implementations remain supported.
- Python documentation and the runnable quickstart demonstrate the API.
- Full Python test/lint validation and final diff review are complete, with
  limitations recorded rather than inferred.

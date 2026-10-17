# Implementation Plan

## Issue and SPEC

[#31 — HTTP connection optimization, retry strategy, and MCP session scope](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/31)

[Approved SPEC](./SPEC.md)

## Objective

Reuse lifecycle-managed HTTPX clients for runtime-managed Python OIDC/JWKS,
MCP, and OBO calls; preserve per-agent/per-server configuration and lazy MCP
sessions; and add bounded retry and service-scoped circuit-breaker behavior.
Do not start implementation until this PLAN is approved.

## Repositories and prerequisites

- Repository: `ai-enterprise-agent-runtime` only.
- SPEC approval has been received; implementation remains gated on approval of
  this PLAN.
- After approval, create `feature/31-http-client-lifecycle` from `main` aligned
  with `origin/main`, carrying the approved SPEC, PLAN, and issue index update.
  Preserve unrelated working-tree changes.

## Library decision: retry and circuit breaker

- **Retry: use Tenacity**, behind typed runtime policy objects. It supports
  synchronous and asynchronous retry loops and avoids maintaining backoff,
  deadline, and retry-predicate mechanics ourselves. Every use must explicitly
  set a finite attempt limit, bounded backoff, eligible exception/status
  categories, and the remaining request deadline; no unconfigured/default
  retry decorator is acceptable. Keep it optional and available only with the
  relevant outbound HTTP extras.
- **Circuit breaker: implement a small typed internal state machine.** The
  runtime needs a narrow contract: one state per stable upstream identity,
  shared by concurrent callers, one half-open probe, configurable threshold
  and cooldown, and no caller data in diagnostics. A general dependency would
  still need adapters for those identity and lifecycle rules. The available
  `aiobreaker` release history is stale, so adopting it would add maintenance
  and compatibility risk without removing the service registry/integration
  code. Keep the state machine small, thread-safe, and directly covered in
  sync and async paths.
- **Dependency boundary:** retain HTTPX and Tenacity as optional dependencies.
  Add an optional remote-OIDC/JWKS extra to `security`; retain HTTPX and add
  Tenacity to the `agents[mcp]` extra. Do not make base runtime imports require
  HTTPX, Tenacity, or the MCP SDK. Confirm the precise extra names and minimum
  supported Tenacity version against the packaging conventions before editing
  package metadata.
- **Retry defaults proposed for implementation:** at most 3 total attempts,
  with bounded exponential backoff (100 ms initial, 500 ms maximum plus jitter)
  within the existing operation deadline. MCP tool execution is excluded.
  Count one final failed operation toward the breaker after retries are
  exhausted, rather than counting each internal attempt.
- **Breaker defaults proposed for implementation:** open after 5 consecutive
  failed operations for 30 seconds, then allow exactly one half-open probe;
  success closes the breaker and failure reopens it. All values are typed and
  configurable. Confirm these defaults during implementation against the
  existing MCP (30 s) and OBO (10 s) timeouts.
- **Configuration location:** expose optional typed `retry` and
  `circuit_breaker` settings in each HTTP MCP server's YAML configuration, next
  to that server's network and timeout settings. Omitted values use the
  documented defaults. MCP tool calls remain non-retryable regardless of YAML
  settings. OIDC discovery/JWKS use JWT/OIDC authentication configuration, not
  an MCP server file. OBO targets a separate token service, so its breaker
  identity is that token service; its policy uses the containing MCP server's
  retry/breaker settings unless the existing schema justifies an explicit OBO
  override during implementation.

References: [Tenacity documentation](https://tenacity.readthedocs.io/en/stable/index.html),
[aiobreaker usage](https://aiobreaker.netlify.app/usage.html), and
[aiobreaker release history](https://pypi.org/project/aiobreaker/).

## Constitution Check

- **Parity:** PASS with the SPEC's explicit exception. This issue changes the
  Python HTTPX paths only; it does not claim .NET or Java parity.
- **Reuse and simplicity:** PASS. Extend `McpConnection`,
  `McpAgentRegistry`, the RFC 8693 token source, `OidcDiscovery`, and JWT key
  resolution. Use Tenacity for retry mechanics; add only the typed lifecycle
  and breaker abstractions missing from the repository. Keep sync JWT/OIDC and
  async MCP lifecycles distinct while applying the same typed policy contracts.
- **Reuse evidence:** No existing retry or breaker implementation was found.
  Existing MCP registry ownership and OAuth injection are the extension points;
  JWT currently delegates key fetching to PyJWT's `PyJWKClient`, and discovery
  uses `urllib`. Confirm the pinned MCP SDK's HTTP client factory and close
  semantics before choosing the final injection shape.
- **Testing:** PASS when implemented test-first. Add focused unit and
  integration coverage for typed settings, lifecycle ownership, retry and
  breaker behavior, JWT/OIDC HTTP behavior, MCP result semantics, concurrency,
  and optional dependency boundaries. .NET/Java parity tests are out of scope
  under the approved SPEC exception.
- **UX consistency:** PASS. Preserve current public authentication and MCP
  call/result contracts; document which operations can retry and expose
  server-specific validation errors without credentials.
- **Performance:** PASS subject to measuring the SPEC budgets: under 1 ms p95
  closed-breaker overhead, under 10 ms p95 open-breaker rejection, no retries
  beyond an operation deadline, and pool limits respected with 100 concurrent
  operations.
- **Observability and security:** Use package-standard loggers; report only
  service identity/category and breaker state. Never log tokens, request bodies,
  provider response bodies, or raw provider exceptions.
- **Domain organization and typing:** Put shared typed retry/breaker policy
  contracts in a reusable Python runtime domain at the lowest existing package
  layer that avoids dependency cycles; keep MCP pool construction in `agents`
  and OIDC/JWKS client ownership in `security`. Use dataclasses/enums and a
  declared protocol for injectable ownership; no untyped policy maps.
- **Examples and docs:** Update the Python MCP and security guides, MCP-server
  authentication guide, and runnable LangChain MCP example as required by the
  SPEC.

## Scope and anticipated components

- `packages/python/security/pyproject.toml` and
  `packages/python/agents/pyproject.toml`: optional HTTP/retry dependencies.
- `packages/python/agents/ygo74/agent_runtime/domains/mcp/configuration.py` and
  `packages/python/agents/ygo74/agent_runtime/domains/configuration/schemas/mcp-server.schema.json`:
  validate and load typed per-server retry/breaker YAML settings without
  exposing sensitive values.
- `packages/python/security/ygo74/agent_runtime/domains/auth/oidc_discovery.py`
  and `jwt_authenticator.py`: HTTPX-backed discovery and JWKS retrieval while
  retaining synchronous authentication entry points and key caching.
- A small typed runtime HTTP/resilience domain in `packages/python/security/`
  (or another already-shared Python package if dependency inspection finds a
  better existing home): shared policy values, per-service breaker state, and
  sync/async lifecycle-facing interfaces. Do not introduce a new distribution.
- `packages/python/agents/ygo74/agent_runtime/domains/mcp/binding.py` and
  `registry.py`: lazy HTTP client creation and one owned async pool per distinct
  HTTP server configuration in the agent registry; skills sharing a server
  reuse the connection/client; preserve proxy, timeout, TLS, headers, OAuth,
  context isolation, and injected-client ownership.
- `packages/python/agents/ygo74/agent_runtime/domains/auth/oauth_token_exchange.py`:
  use the server's managed client for default OBO exchange and apply only the
  safe bounded retry/breaker policy.
- `tests/unit/python/` and `tests/integration/python/`: extend existing MCP,
  OAuth, and JWT test modules where appropriate; add a deterministic local MCP
  server and isolated policy tests. Add or extend
  `tests/performance/python/test_mcp_registry_budget.py` for pool concurrency
  and breaker overhead.
- `doc/python/mcp.md`, `doc/python/security.md`,
  `doc/users/mcp-server-hosting.md`, and the runnable sample under
  `samples/python/python-langchain-fastapi/06-mcp-configuration/`.

## Steps

### Step 1 — Confirm client and package integration constraints

- Inspect the pinned MCP SDK transport factory to confirm how one `AsyncClient`
  can be reused across sessions and closed once by the registry.
- Trace the authentication composition points for `JwtAuthenticator`,
  `OidcDiscovery`, and MCP-server JWT validation. Select typed sync and async
  lifecycle interfaces without changing synchronous auth APIs or creating a
  package dependency cycle.
- Confirm Tenacity's supported runtime/Python compatibility and optional-extra
  installation paths. Record any required adjustment to the dependency choice
  before implementation; a material scope change returns for approval.

### Step 2 — Define typed resilience policies and lifecycle ownership

- Add validated retry settings (attempt cap, backoff bounds, operation deadline)
  and breaker settings (failure threshold, open duration) with conservative
  defaults.
- Implement and unit-test closed/open/half-open transitions, one-probe recovery,
  shared per-service identity, separate-service isolation, and concurrency-safe
  updates. Keep breaker state independent from client pool identity.
- Provide sync and async retry adapters over Tenacity. Retry only explicitly
  classified transport failures and safe setup/read operations. Propagate
  cancellation and stop when the remaining deadline cannot accommodate another
  attempt.
- Define owner/injection/close semantics: caller-injected clients remain
  caller-owned; runtime-created clients close exactly once after dependents.

### Step 3 — Move JWT/OIDC discovery and JWKS to managed HTTPX

- Replace `urllib` discovery and PyJWT-owned JWKS fetching with HTTPX-backed
  retrieval through the shared synchronous authentication lifecycle.
- Retain issuer/JWKS URL validation, configured timeout/TLS behavior, key-set
  caching, and synchronous authenticator APIs.
- Apply the same service-scoped retry and breaker policies to discovery and
  JWKS reads; redact provider and credential details in errors/logs.
- Preserve base-package optionality and cover MCP server JWT validation through
  the shared security package.

### Step 4 — Reuse one async client per agent MCP server

- Update registry construction so each distinct HTTP MCP server gets one lazy
  HTTPX pool; skills referencing that server share it, and separate agent
  registries/server definitions remain isolated.
- Apply the server's configured proxy and request timeout to its pool, keep TLS
  verification enabled, and preserve per-request headers/context and OBO
  principal session partitioning.
- Load each server's typed retry/breaker policy from its YAML declaration;
  leave tool execution non-retryable even when retries are enabled for safe
  setup operations. Keep JWT/OIDC policy configuration outside MCP YAML.
- Route default RFC 8693 token exchange through that server's client; do not
  create or close a per-exchange client when the managed client is available.
- Keep tool execution outside automatic retries. Preserve empty, error, and
  structured MCP result fields as returned by the SDK.

### Step 5 — Add test-first integration and performance coverage

- Add failing tests before implementation for ownership/reuse, injected-client
  ownership, lazy sessions, multi-user context isolation, server-specific pool
  settings, OIDC/JWKS retrieval, bounded retry/exhaustion/deadline, and breaker
  transitions/sharing/isolation.
- Exercise MCP success, `isError`, empty-content, and `structuredContent`
  responses against a local deterministic server. Prove there is no tool-call
  replay after ambiguous transport failure and no retry for protocol or
  application errors.
- Validate under 100 concurrent operations that each per-server pool respects
  its configured connection limit; measure closed/open breaker budgets from the
  SPEC. Avoid public network services and provider credentials.
- Verify imports and installation boundaries with agents/security base installs
  lacking HTTPX/MCP, and with the relevant extras installed.

### Step 6 — Document lifecycle and review the full change

- Explain one HTTPX async pool per MCP server per agent registry, the separate
  shared sync JWT/OIDC client, startup/shutdown ownership, injected clients,
  retry bounds, breaker behavior, per-server proxy/timeouts, and actual MCP
  result semantics.
- Update the runnable Python MCP configuration example to show registry
  lifecycle use and one-or-two-server-per-agent guidance without credentials.
- Review public API/backward compatibility, docs and sample links, package
  optionality, logging redaction, `git diff --check`, and the full diff.

## Validation plan

After implementation, use repository CI checks for Ruff, the Python unit and
integration suites, and Python package builds; execute the targeted MCP, OAuth,
JWT/OIDC, optional-dependency, and performance tests first. Run no public-service
tests. No tests are being added or run during this planning stage.

## Risks and mitigations

- **MCP SDK client-factory constraints:** verify before adapting transport
  internals; retain a single registry close owner and prove it with lifecycle
  instrumentation.
- **Sync/async lifecycle mismatch:** keep the synchronous auth API and
  asynchronous MCP clients in their natural event-loop/thread contexts; do not
  share an `AsyncClient` across loops.
- **Retries obscuring outcomes:** never retry MCP tools; constrain retries to
  explicit transport exceptions on safe reads/setup and the approved OBO
  exchange. Enforce one end-to-end deadline.
- **Breaker state fragmentation:** key by stable upstream service identity and
  keep the state registry independent of HTTP client instances and caller
  identity.
- **Connection growth:** client pools are per server and per registry; retain
  explicit connection limits and document the recommended one or two MCP
  servers per agent.
- **Dependency creep:** optional dependencies remain behind the features that
  use them; keep the breaker implementation small and avoid adding a dedicated
  circuit-breaker package.

## Completion criteria

- Every acceptance criterion in [SPEC.md](./SPEC.md) is met.
- Same-agent skills and OBO sessions reuse the configured server client; other
  server definitions and agents do not; JWT/OIDC uses its own shared sync
  client; clients close once at their owning lifecycle boundary.
- Retry and breaker policies are bounded, typed, service-scoped, observable
  without secret leakage, and tested across sync and async paths.
- MCP tool results, errors, lazy setup, and principal isolation preserve the
  approved contracts.
- User guides and the runnable example explain lifecycle, configuration, retry,
  breaker, and result behavior; optional dependency boundaries remain intact.
- Targeted tests, performance budgets, package builds, lint, and
  `git diff --check` pass before PR readiness.

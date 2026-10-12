# Implementation Plan

## Issue

[#27 — chargement configuration MCP](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/27)

## Specification

[SPEC.md](./SPEC.md)

## Objective

Extend the Python MCP client configuration path so skill and server YAML share
versioned schemas, secret references resolve safely, HTTP connection settings
include proxy support, and an agent-level registry loads and reuses only the
servers referenced by its skills.

## Preconditions

- The Issue 27 SPEC is approved.
- Work is limited to `/data/repos/ai-enterprise-agent-runtime`; the MCP server
  hosting distribution and .NET/Java packages are not changed.
- Implementation work starts on `feature/27-mcp-configuration`, based on
  `origin/main`. The approved SPEC and this PLAN are preserved as task records.
- Preserve the current public constructors and behavior of
  `McpServerBinding`, `McpServerBindingLoader`, `McpConnection`, and
  `DialectRegistry` for direct composition callers.
- Proposed public configuration API: `McpServerConfigurationLoader` loads one
  typed `McpServerConfiguration`; `McpAgentRegistryLoader` builds one
  `McpAgentRegistry` from an `AgentManifest` and configuration directory;
  `McpAgentRegistry.for_skill(tool_name)` returns a typed skill-specific view
  with only its allowed tool mappings and shared server connection. The view
  rejects lookup of tools outside its allow-list. Existing direct
  `McpConnection` use remains an explicitly application-controlled low-level
  API.
- Confirm the proxy-client injection API provided by the pinned `mcp>=1.24,<2`
  SDK before choosing the concrete `httpx.AsyncClient` lifecycle. Do not widen
  the MCP SDK version range as part of this issue.

## Constitution Check

- **Cross-language parity:** PASS. The existing MCP client is Python-only in
  this repository. This issue adds configuration to that existing Python-only
  surface and does not claim new .NET/Java behavior.
- **Reuse and simplicity:** PASS. Extend `SkillManifestInput`,
  `SkillManifestLoader`, `YamlDocument`, `ManifestSchemas`,
  `McpServerBindingLoader`, and `McpConnection` where their responsibilities
  fit. Reuse `ConfigurationDirectory`, `EnvironmentFile`, the MCP OAuth
  helpers, and the existing async connection lifecycle. Add a cohesive typed
  server-configuration/agent-registry abstraction only where no current type
  represents that responsibility; do not put configuration parsing into the
  dialect registry.
- **Test-first:** PASS. Add failing schema, secret-resolution, loader,
  registry, transport, and performance tests before changing their
  implementations. Preserve and rerun existing MCP plumbing tests.
- **Typed contracts:** PASS. Represent transport, authentication mode, network
  settings, server configuration, and skill-to-server views with typed models
  and enums. Keep untrusted YAML mappings only at the parser boundary and
  convert them to typed objects after JSON Schema and model validation.
- **UX and examples:** PASS. The packaged JSON Schemas are used for both editor
  guidance and runtime validation. Update the public MCP guide and add a
  runnable configuration example demonstrating shared and distinct servers.
- **Performance:** PASS with measured budgets from the SPEC: registry
  construction under 100 ms p95 for 20 skills/10 server files (excluding
  network/OAuth), and per-skill registry lookup plus tool allow-list check
  under 1 ms p95.
- **Reuse evidence:** Existing code reviewed: `YamlDocument`,
  `ManifestSchemas`, `SkillManifestInput`, `SkillManifest`,
  `SkillManifestLoader`, `ConfigurationDirectory`, `EnvironmentFile`,
  `McpServerBinding`, `McpServerBindingLoader`, `McpConnection`,
  `DialectRegistry`, `PinnedScopeOAuthProvider`, and `FileTokenStorage`. The
  implementation will extend these contracts and add only the missing
  configuration and agent-scoped registry types.

## Scope and anticipated files

**Repository:** `ai-enterprise-agent-runtime` only.

**Python package:**

- `packages/python/agents/ygo74/agent_runtime/domains/configuration/manifest_inputs.py`
- `packages/python/agents/ygo74/agent_runtime/domains/configuration/manifests.py`
- `packages/python/agents/ygo74/agent_runtime/domains/configuration/manifest_schemas.py`
- `packages/python/agents/ygo74/agent_runtime/domains/configuration/schemas/skill.schema.json`
- `packages/python/agents/ygo74/agent_runtime/domains/configuration/schemas/mcp-server.schema.json`
- `packages/python/agents/ygo74/agent_runtime/domains/contracts/manifests.py`
- `packages/python/agents/ygo74/agent_runtime/domains/mcp/binding.py`
- `packages/python/agents/ygo74/agent_runtime/domains/mcp/oauth.py` only if a
  small adapter is required to assemble the existing OAuth primitives from
  typed configuration.
- New cohesive typed MCP configuration, secret-resolution, and agent-registry
  modules under `packages/python/agents/ygo74/agent_runtime/domains/mcp/`.
- Expose the MCP server schema through `ManifestSchemas` alongside the existing
  agent and skill schemas. The existing `schemas/*.json` package-data rule
  already includes it.
- Update `packages/python/agents/pyproject.toml` for JSON Schema validator and
  dotenv dependencies in the optional `configuration` and `mcp` install paths
  that use them. Keep both dependencies out of the base install.

**Tests:**

- `tests/integration/python/test_mcp_plumbing.py`
- `tests/integration/python/test_manifest_configuration_schemas.py`
- New focused tests for MCP server configuration, secret resolution,
  agent-level server registry, and transport setup under
  `tests/integration/python/`.
- `tests/performance/python/` and
  `tests/performance/baselines/performance_thresholds.json` for the new
  configuration and per-skill lookup budgets.
- Existing package boundary, public surface, and Python test suites for
  backward compatibility and optional-dependency behavior.

**Documentation and example:**

- `doc/python/mcp.md` and `doc/python/README.md`.
- `samples/examples/python-langchain-fastapi/` plus its example index, with
  configuration files and a runnable loader smoke path that does not require a
  remote MCP server or live OAuth consent merely to validate the configuration.

## Steps

### Step 1 — Extend the typed skill contract and ship runtime-used schemas

**Objective:** Let a skill manifest identify its MCP server, and make the
versioned schemas the runtime validation source for both skill and server YAML.

**Tests first:**

- Add schema tests for optional `mcp_server`, the dependency between
  `mcp_server` and non-empty `mcp_tools`, and compatibility for existing skills
  without MCP fields.
- Add server-schema fixtures for HTTP and stdio, each authentication mode,
  timeout, network proxy settings, and existing binding fields.
- Add runtime-loader tests showing that schema-invalid fields and values fail
  with a path and field error before typed object construction.
- Add a schema package-resource test for wheel-visible skill and MCP server
  schema files.

**Implementation:**

- Extend `SkillManifestInput` and `SkillManifest` with optional `mcp_server`,
  and transfer it in `SkillManifestLoader` without changing skills that do not
  use MCP.
- Extend the skill schema and add a versioned MCP server JSON Schema. Expose
  the latter through `ManifestSchemas`; include the documented YAML Language
  Server annotations in example files.
- Reuse `YamlDocument`/`ManifestSchemas` or add the smallest shared
  `JsonSchemaValidator` responsibility needed to validate raw YAML against the
  packaged schema before Pydantic models. Keep schema error output concise and
  path-aware; never include resolved secret values.
- Add JSON Schema and dotenv dependencies only to the optional configuration
  and MCP installation paths that use them. Keep unrelated runtime imports
  free of YAML, MCP, HTTP-client, dotenv, and schema-validator imports.

**Validation:**

- Schema fixtures validate independently with Draft 2020-12.
- Runtime skill and server loaders use the same schema documents as editor
  tooling and reject unknown properties and invalid types/enums.
- Existing skill manifests without `mcp_server` still produce equivalent
  `SkillManifest` values.

### Step 2 — Load typed server settings and resolve secrets safely

**Objective:** Parse supported MCP server YAML into typed configuration and
construct the existing binding/authentication inputs without moving secrets
back into configuration files.

**Tests first:**

- Cover valid and invalid HTTP/stdio endpoint settings and incompatible
  transport/authentication combinations.
- Cover `${ENV_VAR}` resolution in the API-key value and OAuth client secret,
  plus rejection of malformed, missing, and empty references.
- Assert resolved secret contents do not appear in typed object `repr`,
  exception text, validation diagnostics, or captured logs.
- Cover `EnvironmentFile` non-overriding behavior and deterministic injected
  environment mappings.
- Cover OAuth configuration assembly with `PinnedScopeOAuthProvider` and
  `FileTokenStorage` using fakes; do not launch a browser or consent listener.

**Implementation:**

- Introduce typed enums/models for authentication, credentials, OAuth
  settings, and server configuration. Extend the existing binding loader or
  add a thin YAML-to-typed-configuration loader while retaining its current
  generic capability validation and public constructor behavior.
- Resolve only the two designated credential fields. Load the delivered `.env`
  from the directory adjacent to the configured `config/` root through the
  existing `EnvironmentFile` behavior when using the agent registry entry
  point, with process values taking precedence; allow an explicit environment
  mapping for deterministic callers/tests. Keep dotenv optional and loaded
  only by this configuration path.
- Convert API-key settings to redacted HTTP headers and build OAuth settings
  from the existing pinned-scope/token-storage helpers. Keep non-secret OAuth
  settings, timeout, transport, and tool mappings in YAML.
- Add path-traversal-safe resolution of a server configuration name beneath
  `config/mcp/`; do not allow absolute paths or `..` to select another file.
- Preserve all currently accepted `McpServerBindingLoader` YAML fields and
  error factory semantics. If strict schema validation requires migration of a
  previously accepted shape, document that migration before changing it.

**Validation:**

- Valid YAML produces typed, redacted settings and a compatible existing
  binding.
- Missing credentials fail at setup with a field name and variable name only;
  the supplied value is never echoed.
- Existing direct binding-loader tests continue to pass.

### Step 3 — Apply HTTP timeout and proxy settings to connections

**Objective:** Apply typed network settings to streamable HTTP while preserving
stdio behavior and the lazy single-session lifecycle.

**Tests first:**

- Mock the pinned SDK transport and HTTP client constructor. Verify URL,
  headers/OAuth, timeout, proxy client, and close ordering are forwarded.
- Verify stdio command, args, and environment remain unchanged and no HTTP
  client or proxy is created for stdio.
- Verify malformed or unsupported proxy URLs fail before a connection is
  opened; verify representations/logs do not expose credential-bearing
  material.
- Cover close behavior after successful connection, failed initialization, and
  repeated close.

**Implementation:**

- Extend `McpConnection` additively with typed network configuration while
  preserving current constructor defaults and redacted header behavior.
- Use the proxy injection point supported by the pinned MCP SDK to pass a
  configured HTTP client. Own that client's lifetime in the same
  `AsyncExitStack` as the MCP transport and session; keep the lazy-connect lock
  and cleanup ordering intact.
- Apply `request_timeout_seconds` to the existing HTTP and MCP session timeout
  settings. Do not pass HTTP-only options into stdio.

**Validation:**

- Mocked connection tests prove the configured proxy and timeout reach the
  HTTP request path and all owned resources close once.
- Existing concurrent lazy-session and failure-cleanup behavior remains
  covered by MCP plumbing tests.

### Step 4 — Build an agent-scoped, skill-aware server registry

**Objective:** Load only server configurations named by an agent's skills,
share each server connection within that agent, and expose a constrained
skill-specific view.

**Tests first:**

- Two skills referencing one name load one server config and share one
  connection/close lifecycle; a third skill referencing another name creates a
  distinct entry.
- Unreferenced server YAML is not read; unknown names, path traversal,
  duplicate conflicting skill identities, missing tool mappings, and
  unsatisfied `mcp_tools` declarations fail during registry construction.
- A skill-specific view resolves only aliases in that skill's allow-list even
  when another skill sharing the same server can access more tools.
- Closing the registry closes every unique connection once, including partial
  setup failure; lookups after close fail clearly.
- Exercise a valid multi-skill fixture through the documented public loader
  API without opening a network connection.

**Implementation:**

- Add `McpAgentRegistryLoader` and `McpAgentRegistry`. The loader accepts an
  `AgentManifest` and configuration directory, loads one
  `McpServerConfiguration` and connection per distinct `mcp_server` name, and
  creates skill-specific views over shared entries. `for_skill(tool_name)`
  returns the view for one declared skill and fails on undeclared skills.
- Reuse `McpServerBindingLoader`, `McpServerBinding`, and `McpConnection`; do
  not add MCP execution or dialect translation to the configuration registry.
- Preserve per-skill `mcp_tools` as a restrictive view of the server's
  declared alias/tool mappings. The view exposes only allowed mappings and
  rejects lookup of any other alias, so a consuming dialect can build its
  tools from that view without gaining a sibling skill's additional tools.
  Keep the existing low-level connection API available for explicit
  application-controlled composition; do not add generic MCP tool execution
  or translation in this issue.
- Give the agent registry an explicit asynchronous close operation and
  rollback already-created resources if a later server fails to load.

**Validation:**

- Registry behavior matches the shared/distinct/unreferenced and per-skill
  isolation acceptance cases.
- Construction performs no remote connection or OAuth interaction; transport
  connection remains lazy until the existing connection is used.

### Step 5 — Document configuration, add the example, and measure budgets

**Objective:** Make the new YAML contract discoverable and runnable, validate
the performance budgets, and complete backward-compatibility review.

**Implementation:**

- Update `doc/python/mcp.md` with config layout, skill references, server schema,
  supported authentication, secret references, proxy settings, registry
  lifecycle, optional install extras, and migration guidance for older YAML.
- Add a runnable example with two skills sharing a server and one skill using a
  second server. Include sample `.env.example` values only for API-key and
  OAuth client-secret variables; include schema annotations and a local loader
  smoke command that needs no remote server.
- Add measured performance coverage for registry construction with 20 skills
  and 10 unique server configs and for repeated per-skill view/tool lookup.
  Add named 100 ms and 1 ms thresholds to
  `tests/performance/baselines/performance_thresholds.json`, respectively, and
  follow the repository's existing repeated-sample p95 methodology.
- Update the example index and package resource/dependency metadata as required.

**Validation:**

- Run the targeted MCP/configuration tests and schema tests first, then the
  performance tests and full Python checks below.
- Install the Python package with its documented extras and verify the
  packaged schemas are readable after installation.
- Review the example loader smoke path and docs against public APIs and actual
  configuration files.
- Run `git diff --check` and review the complete diff for unexpected files,
  credential leakage, and accidental changes to non-MCP runtime behavior.

## Validation commands

Run from the repository root after implementation:

```bash
python -m ruff check packages/python tests samples/examples/python-langchain-fastapi
python -m pytest \
  tests/integration/python/test_mcp_plumbing.py \
  tests/integration/python/test_manifest_configuration_schemas.py \
  tests/integration/python/test_mcp_server_configuration.py \
  tests/integration/python/test_mcp_agent_registry.py \
  tests/performance/python/test_mcp_registry_budget.py
python -m pytest tests/ samples/examples/python-agentframework-fastapi/test_agentframework_fastapi_example.py
git diff --check
```

The full Python command follows the current CI workflow. Report any unavailable
external example prerequisites separately; configuration loading itself must
not require live MCP or OAuth services.

## Risks and mitigations

- **Pinned SDK proxy support:** Verify its current supported injection API
  before coding and cover it with a transport-construction test. Keep the SDK
  upper bound unchanged.
- **Strict schema compatibility:** Include every field the existing loader
  currently accepts, add fixtures from current users/examples, and document
  any deliberate migration before implementation.
- **Credential leakage:** Resolve secrets after schema validation, store them
  only in redacted typed values, and test repr, errors, logs, and proxy/header
  representations.
- **Connection ownership:** Construct lazily, register resources with one
  `AsyncExitStack`, unwind partial setup in reverse order, and close each unique
  server entry once.
- **Tool allow-list interpretation:** Match each skill's `mcp_tools` against
  the server's declared aliases at setup. Keep the registry view restrictive
  while preserving the lower-level direct connection API for existing
  application-controlled compositions.
- **Optional dependencies:** Keep MCP, YAML, HTTP, dotenv, and JSON Schema
  imports behind the corresponding optional install paths; retain import-boundary
  tests to ensure unrelated runtime domains stay lightweight.
- **Performance test noise:** Use the repository's existing repeated-sample
  p95 approach and ensure fixtures model file/schema work only, not external
  connections or OAuth.

## Completion criteria

- Every acceptance criterion in [SPEC.md](./SPEC.md) has test or review
  evidence.
- Existing direct MCP APIs, optional dependency boundaries, and skill manifests
  without MCP references remain compatible.
- The examples and docs match the shipped schemas and APIs.
- Python Ruff, targeted MCP/configuration/performance tests, full Python CI
  tests, package-resource checks, and `git diff --check` pass, or their failures
  are reported accurately with remaining risks.

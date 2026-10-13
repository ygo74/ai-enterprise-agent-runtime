# Specification

## Issue

[#27 — chargement configuration MCP](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/27)

## Objective

Let an agent developer describe MCP servers and their use by skills in YAML,
validate those files in the editor and at runtime, and use the runtime's
configuration APIs to build one agent-scoped registry of the servers referenced
by its skills. Resolve credential values from environment variables while
keeping transport, authentication, timeout, and network settings in YAML.

## Context

The Python agents distribution already has an optional MCP client, a YAML
`McpServerBindingLoader`, a reusable `McpConnection`, and an application-owned
`DialectRegistry`. The binding loader validates selected fields in Python but
does not validate files against a packaged JSON Schema. Connection credentials,
OAuth setup, and HTTP request headers are currently supplied by the calling
application. Agent skill manifests are independently validated against a
packaged schema and can declare an `mcp_tools` list, but cannot name an MCP
server.

The issue asks for two linked configuration layers: a skill identifies the MCP
server it uses and the tools it may use; the server file describes how to reach
and authenticate to that server. Several skills may reference one server, and
one agent may reference several servers. The runtime should own loading,
validation, secret resolution, and the per-agent server registry so applications
do not have to rebuild that plumbing.

## Problem

Configuration is split between server YAML, skill YAML, environment variables,
and caller-written composition code. There is no editor-visible server schema,
and runtime validation can accept misspelled or unsupported YAML fields. The
current APIs also do not assemble an agent's skill-to-server references into a
deduplicated registry, or provide common network proxy settings for remote MCP
servers.

## Scope

- Extend the Python `ygo74-agent-runtime-agents` MCP client/configuration APIs.
  The repository currently provides MCP client and server APIs only in Python;
  .NET and Java MCP parity is not part of this issue and is not claimed by it.
- Add an optional `mcp_server` configuration-name field to a skill manifest.
  Each skill may refer to one server and may declare the MCP tool names it is
  allowed to use in `mcp_tools`. The allow-list narrows the tools available
  through that server; it does not grant capabilities the application has not
  implemented. A skill with MCP tools must name its server; a skill with no MCP
  tools need not name one.
- Load the named server's YAML configuration from the configured MCP directory
  (by default, `config/mcp/<name>.yaml`) and validate it with the same packaged
  JSON Schema used by editor tooling.
- Define the server YAML for supported transports, transport-specific endpoint
  settings, dialect/tool mappings, `authentication_mode` and its settings,
  `request_timeout_seconds`, and HTTP `network` options including a proxy URL.
- Support no authentication, API-key authentication, and OAuth authentication
  for HTTP connections. Secret values in API-key credentials and OAuth client
  secrets are environment references, not literal YAML values. Use the
  `${ENV_VAR}` reference form, resolve it during loading, and fail setup when a
  referenced variable is unset or empty. Non-secret OAuth and network settings
  remain in YAML. OAuth token persistence continues to use a separately
  configured, ignored token file.
- Package versioned JSON Schemas for skill and MCP server YAML. Document the
  YAML Language Server schema annotation so VS Code can report invalid fields,
  missing fields, types, and enum values while editing. Runtime loaders must
  validate against these packaged schemas before constructing typed
  configuration objects.
- Provide an agent-level loader/registry that gathers server references from
  the agent's skills, loads each referenced named server once, and reuses one
  server entry/connection per name within that agent. Unreferenced server files
  are not loaded. Missing references, duplicate conflicting skill identities,
  or a skill/server tool declaration that cannot be satisfied fail during
  setup with a path-aware error.
- Preserve the existing direct `McpServerBinding`, `McpConnection`, and
  `DialectRegistry` composition APIs for callers that construct bindings
  themselves. New configuration APIs compose and reuse those abstractions.
- Update Python MCP documentation and a runnable configuration example.

## Out of scope

- Adding MCP client or server APIs to .NET or Java.
- Changing the separately packaged MCP server-hosting distribution.
- Defining agent-domain tool implementations, executing MCP tools, or deciding
  application authorization policy. The runtime loads configuration and
  enforces declared per-skill tool allow-lists; the application still decides
  which capabilities to implement and how to authorize a caller.
- Loading configuration from remote stores, supporting arbitrary secret
  providers, or adding a general-purpose YAML templating language.
- Changing the OAuth consent flow, granted scopes, token storage format, or
  credential policy beyond connecting the existing OAuth helpers to YAML
  configuration.

## Expected behavior

1. A skill YAML uses `mcp_server` to name its MCP server and `mcp_tools` to list
   the tools available to that skill. The named server file is the sole source
   of transport and connection configuration; applications do not need to
   duplicate these values in `.env`.
2. A server YAML selects a supported transport and includes the required
   endpoint or process settings. Invalid fields, invalid types, missing
   required values, and invalid authentication/transport combinations are
   rejected before an MCP session is opened.
3. Both skill and server files are validated against packaged JSON Schemas at
   load time. Errors identify the file and invalid field without including
   resolved secret values.
4. `${ENV_VAR}` references are resolved only in schema-designated secret
   fields. A missing, empty, or malformed secret reference is a setup error;
   resolved secrets are not included in representations, logs, or validation
   messages.
5. HTTP network settings can configure a proxy for the client connection.
   Request timeout and proxy settings are applied to the HTTP transport and do
   not alter stdio behavior.
6. Building an agent registry loads every referenced server configuration
   exactly once. Skills sharing the same server name point to the same registry
   entry and connection lifecycle; skills referencing different names receive
   separate entries. The registry and its connections can be closed through an
   explicit asynchronous lifecycle operation.
7. A skill cannot invoke a tool outside its declared allow-list, even when the
   same server is shared by other skills. Unknown server names, absent tool
   mappings, or an allow-list inconsistent with the server declaration fail
   before serving requests or presenting tools to a model.
8. Existing callers that construct `McpServerBinding` and `McpConnection`
   directly continue to work without changes.

## Configuration contract decisions

- A skill's `mcp_server` value is a configuration name, not an arbitrary path.
  The loader resolves it beneath the caller-supplied MCP configuration
  directory; it does not accept path traversal or search unrelated locations.
- A skill references one MCP server, matching the issue's singular example.
  An agent can still use multiple servers through different skills.
- Skills' `mcp_tools` is the authorization/availability ceiling for that skill.
  Server-level tool mappings continue to map application aliases to remote MCP
  tool names; the registry must intersect the skill declaration with those
  mappings rather than widening access.
- Only secret fields accept `${ENV_VAR}` references. Other YAML values are
  literal and schema-validated; no recursive string interpolation is provided.
- `authentication_mode` is an enum with `none`, `api_key`, and `oauth` values.
  API-key configuration is a typed object with required `header_name` and
  `value` fields, where `value` is an environment reference; the runtime sends
  that value unchanged in the named HTTP header. OAuth configuration is a typed
  object with client ID, client-secret reference, callback port, scopes,
  token-file location, and optional resource metadata. Only the credential
  values are environment references.
- `request_timeout_seconds` and an optional `network.proxy_url` configure HTTP
  requests. Unsupported proxy schemes and invalid URLs fail validation rather
  than being silently ignored.
- Authentication settings are valid only for HTTP transport. Stdio servers
  receive process configuration from their YAML entry and do not use HTTP
  authentication or proxy settings.

## Acceptance criteria

- Versioned skill and MCP server JSON Schemas are available with the Python
  package, associated with example YAML for VS Code validation, and are the
  schemas used by runtime loading.
- Tests prove valid configurations load into typed objects and malformed or
  unknown fields, missing required values, invalid enums, and incompatible
  transport/authentication combinations fail with actionable file/field
  context.
- Tests prove only designated secret fields are interpolated, unset or empty
  references fail, and secret contents do not appear in object representations,
  log output, or exception text.
- Tests prove API-key, OAuth, timeout, and HTTP proxy settings are passed to the
  appropriate transport construction path, while stdio settings remain
  unaffected by HTTP-only options.
- Registry tests prove shared server references result in one loaded server
  entry and connection lifecycle per agent, distinct references remain
  distinct, unreferenced configurations are ignored, and missing or conflicting
  declarations fail during setup.
- Tests prove a shared server does not let one skill use MCP tools absent from
  that skill's own allow-list.
- Existing direct binding/connection tests pass without caller changes.
- Python MCP user documentation and a runnable example demonstrate two skills
  sharing one MCP server, another skill using a second server, environment
  references for secrets, schema editor support, and proxy configuration.
- The existing MCP client remains optional: importing or using unrelated
  runtime domains does not require the MCP, YAML, or HTTP client dependencies.

## Compatibility and parity

This is a Python configuration and composition enhancement to the MCP client,
which the repository already documents as Python-only. It adds no new
language-neutral runtime capability and makes no claim of .NET or Java MCP
parity. Existing direct Python MCP APIs remain supported. The skill manifest
schema change is additive for skills without an MCP server reference; existing
skills continue loading with no server attached.

## UX consistency criteria

- Editor validation and runtime validation use the same versioned JSON Schema
  contract and report the same accepted values and required fields.
- Configuration errors name the file and field and explain the correction
  without exposing secret values.
- The documented example can be copied into the documented config layout and
  loaded through the runtime API without separate application-written parsing
  or server deduplication.

## Test strategy

- Follow the test-first quality gate: create schema contract tests, secret
  resolution tests, loader/registry tests, and transport-configuration tests
  before implementing behavior.
- Use temporary YAML files and controlled environment mappings for deterministic
  validation; mock MCP transport constructors where network or OAuth
  authorization would otherwise be required.
- Exercise the packaged schemas independently and through the runtime loaders,
  including the documented example configuration.
- Run the Python MCP client and configuration suites, relevant package/type
  checks, and the repository's documented Python validation for changed areas.
- Review startup/per-request work against the performance budget below and run
  the existing MCP tests for backward compatibility.

## Performance budget

- For an agent configuration of up to 20 skills and 10 unique MCP server files
  (each no larger than 100 KB), schema validation and registry construction
  complete within 100 ms p95 on the repository's standard local benchmark
  environment, excluding network connection establishment and OAuth consent.
- Resolving a skill's already-built server entry and checking its tool
  allow-list adds no more than 1 ms p95 to an in-process lookup, excluding MCP
  network latency.
- Server files are loaded once per unique name in one registry build; schemas
  may be cached after first load, but environment secret values are resolved at
  each registry construction so credential rotation takes effect on restart.

## Risks

- The skill/server split changes which file owns per-capability tool declarations.
  Existing fields and API compatibility must be kept clear so that a server
  shared by skills cannot accidentally widen an individual skill's access.
- A schema can reject existing user YAML that the permissive loader accepted.
  The schema must describe the supported current fields and provide path-aware
  errors; configuration format migration must be documented if any current
  accepted shape is intentionally changed.
- Environment interpolation can leak secrets through validation or debug
  output if raw parser values are surfaced. Secret values must be redacted at
  the point of resolution and in typed configuration representations.
- Proxy support differs across MCP SDK and HTTP client versions. The
  implementation must confirm the pinned SDK's supported proxy API and keep
  unsupported schemes out of the contract.
- Reusing one connection across skills requires deterministic agent lifecycle
  ownership so sessions close once and cannot be closed while another skill is
  using the same agent registry.

## Open questions

- None. The configuration names, API-key header semantics, Python-only scope,
  and secret-reference syntax above are the proposed contract to review;
  changes can be requested before approval.

## Approved amendment — OAuth on-behalf-of client settings

The MCP server YAML is also the source of OAuth on-behalf-of client settings.
Under `authentication_oauth_on_behalf_of`, the configuration may include
`token_url`, `client_id`, and `client_secret` alongside `audience` and `scopes`.
The three client settings are optional as a group so an application with a
custom injected source can continue to configure only its audience and scopes.
When the standard client settings are supplied, `client_secret` must be an exact
`${ENV_VAR}` reference and is resolved from the selected runtime environment
when the server configuration is loaded. A source factory requires this full
group. For example:

```yaml
authentication_mode: oauth_on_behalf_of
authentication_oauth_on_behalf_of:
  token_url: https://identity.example.test/realms/agents/protocol/openid-connect/token
  client_id: mail-agent
  client_secret: ${MCP_MAIL_OBO_CLIENT_SECRET}
  audience: mail-mcp
  scopes: []
```

The resolved settings object redacts the secret in its representation and
configuration errors never include its value. The token endpoint must use
HTTPS. No client ID or token endpoint is required in environment variables.

When complete client settings are present, the runtime constructs its standard
RFC 8693 `OAuthOnBehalfOfTokenSource`; this does not choose an identity provider
or perform application policy. `McpAgentRegistryLoader` also accepts a typed
source factory for provider-specific behavior. The existing single injected
source remains supported for callers that intentionally share one source.
Source construction must remain local and must not open a network connection.

Acceptance coverage includes strict schema/editor support for the new fields,
environment-only secret resolution and redaction, path-aware failures for a
missing secret, per-server source-factory delivery, and backwards compatibility
for the existing injected-source path. MCP remains a Python-only runtime
capability; no .NET or Java parity is claimed.

## Approved amendment — generic RFC 8693 implementation in the runtime

The current implementation places `Rfc8693OAuthOnBehalfOfTokenSource` in the
Mail application and exposes the configured values as
`McpDelegatedOAuthSettings`. This keeps a standard OAuth token-exchange protocol
implementation in one consumer and does not provide the generic settings type
expected by other MCP clients.

Move the reusable RFC 8693 HTTP exchange implementation into the generic auth
domain of `ai-enterprise-agent-runtime`, outside the MCP package. Expose its resolved input as
`OAuthTokenExchangeSettings` (token URL, client ID, redacted client secret,
audience and scopes), populated by the MCP YAML loader. The runtime registry
should construct this source by default when those settings are present. Keep
the existing `OAuthOnBehalfOfTokenSource` port, explicit source injection and
custom source factory for applications that need provider-specific behavior.
Preserve `McpDelegatedOAuthSettings` as a compatibility alias if needed by
callers of the current branch API.

Mail should consume the runtime implementation and retain only application
composition plus its explicit source override. The runtime implementation must
keep HTTPS-only token endpoints, TLS certificate validation, redacted provider
errors, bearer-token and audience validation, and a bounded HTTP client
lifecycle. Tests use a fake HTTP transport and must not contact an identity
provider. The user approved this ownership change on 2026-10-13.

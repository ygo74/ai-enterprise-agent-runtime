# Issue 27 Follow-up: MCP Headers and OBO Implementation Plan

**Status**: Validated; PR #28 updated and unmerged.

## Issue and specification

- Issue: [#27 — MCP client configuration](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/27)
- Specification: [HEADERS-SPEC.md](./HEADERS-SPEC.md)
- Existing pull request: [#28](https://github.com/ygo74/ai-enterprise-agent-runtime/pull/28)

## Objective

Add arbitrary HTTP headers and user-scoped OAuth delegation to configured MCP
servers. Keep the MCP client reusable across turns while associating each
outbound MCP request with the correct principal, request ID, conversation ID,
and validated subject token. Exchange the subject token for one intended for
the configured MCP audience; never forward it directly.

## Technical context

- The Python MCP client lives in `packages/python/agents/` and pins
  `mcp>=1.24,<2`. Current `authentication_mode: oauth` performs a separate
  authorization-code flow for the MCP client and stores that client's token in
  a file. It does not delegate the token used to authenticate the user to the
  agent.
- `packages/python/security/.../auth/tokens.py` defines redacted `AccessToken`
  and the existing credential-free `DelegatedTokenSource(principal, audience)`
  port. Preserve that public contract. Add a distinct
  `OAuthOnBehalfOfTokenSource` accepting a typed request with principal, verified
  subject token, audience, and scopes. No identity-provider-specific exchange
  implementation is included; the host supplies the OBO source.
- `JwtAuthenticator` validates the incoming bearer token and currently returns
  only projected identity. `fastapi_endpoints._build_raw_payload` serializes
  `AuthenticatedUserContext.to_dict()` and discards the credential before
  calling the agent entrypoint. The internal endpoint path needs to retain a
  redacted `AccessToken` separately from the normalized payload, only after
  successful bearer authentication.
- `ConversationTurn` has principal, conversation ID, and message, while
  `ConversationEntrypoint` creates request correlation. The entrypoint can
  scope a typed invocation context around non-streaming execution and each
  streaming pull without adding credentials to the turn or handler payload.
- The pinned Streamable HTTP SDK sends MCP messages through a long-lived
  background writer task. A plain `ContextVar` lookup in an HTTPX request hook
  can therefore read the context captured at connection startup. Associate
  each session message's JSON-RPC request ID with its typed invocation context
  at the session write boundary; the HTTP request hook can then resolve the
  correct context for that POST, perform a delegated exchange, and render the
  request's configured headers.

## Constitution check

- **Parity:** PASS with the approved Python-only scope. MCP configuration is a
  Python-only capability in this repository; this follow-up adds no .NET/Java
  MCP API or parity claim.
- **Reuse and simplicity:** Extend the existing authentication, access-token,
  MCP configuration, MCP connection, and conversation seams. Preserve
  `DelegatedTokenSource`; add a separate OBO source port and reuse `AccessToken`,
  the MCP SDK request IDs, and the `McpConnection` HTTPX factory. Do not create
  a second token model, parallel MCP transport, or provider-specific OBO
  implementation.
- **Typed contracts:** Represent delegation input, invocation scope, and header
  templates as explicit dataclasses/models. Keep raw payload dictionaries at
  endpoint boundaries only; never use them as an internal token container.
- **Test-first:** Add failing auth-boundary, schema/loader, context-isolation,
  delegated-source, and fake-transport tests before implementation. Prove the
  subject token never appears in serialized payloads, prompts, logs, or errors.
- **UX and examples:** Version the HTTP header and `oauth_on_behalf_of` contract
  in the package schema, MCP guide, and runnable Python example. Keep the
  separate authorization-code `oauth` mode documented and backward compatible.
- **Performance:** Header rendering and request-context association remain
  below 1 ms p95 per outbound request, excluding the delegated token exchange
  and network latency. The injected source owns exchange caching and latency.
- **Reuse evidence:** Reviewed for extension: `AccessToken`,
  `DelegatedTokenSource`, `AuthenticatedUserContext`, `JwtAuthenticator`,
  `RequestAuthenticator`, `fastapi_endpoints._build_raw_payload`,
  `ConversationTurn`, `ConversationEntrypoint`, `McpServerConfigurationLoader`,
  `McpConnection`, `_ProxyHttpClientFactory`, and existing auth/MCP/conversation
  tests.

## Scope and files

**Repository:** `ai-enterprise-agent-runtime` only. Continue on
`feature/27-mcp-configuration` and update PR #28 after validation. Do not merge
or force-push.

**Authentication and request context:**

- `packages/python/security/ygo74/agent_runtime/domains/auth/tokens.py`
- A typed internal verified-request context under
  `packages/python/security/ygo74/agent_runtime/domains/auth/` or
  `packages/python/agents/ygo74/agent_runtime/domains/contracts/`; keep its
  credential out of public exchange payloads and `AuthenticatedUserContext.to_dict()`.
- `packages/python/security/ygo74/agent_runtime/domains/auth/authenticator.py`
- `packages/python/security/ygo74/agent_runtime/domains/auth/jwt_authenticator.py`
- `packages/python/agents/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py`
- `packages/python/agents/ygo74/agent_runtime/domains/contracts/conversation.py`
- `packages/python/agents/ygo74/agent_runtime/domains/endpoints/conversation_payloads.py`
- `packages/python/agents/ygo74/agent_runtime/domains/endpoints/conversation_entrypoint.py`

**MCP configuration and transport:**

- `packages/python/agents/ygo74/agent_runtime/domains/configuration/schemas/mcp-server.schema.json`
- `packages/python/agents/ygo74/agent_runtime/domains/mcp/configuration.py`
- `packages/python/agents/ygo74/agent_runtime/domains/mcp/binding.py`
- `packages/python/agents/ygo74/agent_runtime/domains/mcp/registry.py`

**Documentation, example, tests, and performance:**

- `doc/python/mcp.md` and `doc/python/README.md`.
- `samples/examples/python-langchain-fastapi/08-mcp-configuration/` YAML,
  README, and offline smoke loader.
- Extend auth/JWT, FastAPI endpoint, MCP configuration, registry, plumbing,
  conversation, and endpoint tests under `tests/integration/python/`.
- Extend `tests/performance/python/test_mcp_registry_budget.py` or add a
  focused header-rendering budget; update
  `tests/performance/baselines/performance_thresholds.json` if required.

## Steps

### 1. Define and test the delegated-token request contract

**Tests first:** Verify a typed exchange request contains the authenticated
principal, redacted subject `AccessToken`, target audience, and configured
scopes. Verify token representations redact contents and a source returning an
unexpected audience is rejected. Preserve the existing `AccessToken` type and
avoid introducing another credential representation.

**Implementation:** Preserve the existing credential-free
`DelegatedTokenSource(principal, audience)` API. Add a separate
`OAuthOnBehalfOfTokenSource` receiving the typed exchange request. Document that
OBO implementations perform provider-specific exchange and caching and return a
token for the requested audience. Keep both ports network-agnostic and testable
with fake sources.

### 2. Preserve the validated subject token outside serialized request data

**Tests first:** Cover successful bearer authentication, rejected bearer
credentials, API-key authentication, and absent credentials. Assert the
subject token reaches only the internal delegation scope after successful
bearer authentication. Assert `AuthenticatedUserContext.to_dict()`, normalized
handler payloads, representations, logs, and errors contain no raw token.

**Implementation:** Refactor the private FastAPI normalization seam to retain
a typed verified-request result alongside its normalized payload. The result
contains the projected `AuthenticatedUserContext` and a redacted `AccessToken`
only when the configured bearer authenticator has validated it. Preserve the
existing public authenticator and payload shapes where possible. Scope the
credential around `agent_entrypoint` execution, then capture it into the
per-turn invocation context before returning a stream. API-key and anonymous
authentication produce no subject token.

### 3. Add HTTP headers and the delegated-auth configuration mode

**Tests first:** Add schema and loader cases for static headers, exact
`${ENV_NAME}` values, context tokens, HTTP-only restrictions, invalid header
names/values, unknown tokens, and case-insensitive conflicts. Cover
`oauth_on_behalf_of` audience/scopes, rejected stdio use, missing source, and
exclusive configuration relative to API-key, existing OAuth, and custom
`Authorization` headers. Assert all configured values remain redacted.

**Implementation:** Add optional `headers` and typed
`oauth_on_behalf_of: { audience, scopes }` input to the MCP server model and
Pydantic-generated JSON Schema. Resolve static/environment values at load and
retain typed dynamic templates for request time. Keep the existing
authorization-code OAuth configuration as a separate mode. Inject the
`OAuthOnBehalfOfTokenSource` through `McpAgentRegistryLoader` to connections that
select OBO; fail closed if the source is absent.

### 4. Propagate per-turn context across the MCP SDK writer task

**Tests first:** Through one shared fake MCP session, issue overlapping
JSON-RPC requests for different principals, subject tokens, request IDs, and
conversation IDs. Assert each HTTP POST gets the correct configured headers
and only the exchanged MCP token. Cover source rejection, exchange exceptions,
wrong audience, cancelled/failed requests, and cleanup. Ensure no request falls
back to the incoming subject token or a token cached for another principal.

**Implementation:** Add a typed invocation context containing principal,
subject token, request ID, and conversation ID. Propagate correlation through
`ConversationTurn` compatibly, and scope this context in
`ConversationEntrypoint` around non-streaming execution and each streaming
pull. Wrap the MCP session write stream so each JSON-RPC request ID maps to the
invocation context active when the application issued that request. In the
  HTTPX request hook, resolve the matching context, call
  `OAuthOnBehalfOfTokenSource` with the subject token and configured audience/scopes,
verify the returned audience, set only that result as `Authorization: Bearer`,
and render configured templates. Keep static headers on client defaults,
preserve MCP protocol headers, and bound/clear request-context entries on
response, expiry, and connection close.

### 5. Update docs and the runnable example

Document the exact identity/request tokens, static and environment values,
`oauth_on_behalf_of` configuration, source injection, token exchange boundary,
and distinction from authorization-code OAuth. Demonstrate headers and an
offline fake delegated source; the smoke path must not open a network
connection, browser, or real consent flow.

### 6. Validate, review, and update PR #28

Run the auth, endpoint, MCP, public-surface, performance, Ruff,
packaging/schema, and example checks listed in the approved SPEC and above.
Review concurrency isolation, source/audience validation, token redaction,
package boundaries, and the full diff. Update the implementation record and
PR #28 with actual behavior and validation results. Keep PR #28 unmerged.

## Risks and mitigations

- **Subject-token leakage:** Keep `AccessToken` in an internal verified request
  context; exclude it from serialized payloads, prompts, logs, representations,
  and errors. Send only the token returned by the delegated source.
- **Provider-specific protocol differences:** Inject `OAuthOnBehalfOfTokenSource`;
  do not embed Entra, RFC 8693, or another provider's client flow in the MCP
  package.
- **SDK background task context:** Correlate by JSON-RPC request ID instead of
  reading a request `ContextVar` inside the long-lived sender task.
- **Concurrency and caching:** Scope exchange results to the request context;
  delegate reusable cache policy to the injected source, which must partition by
  principal, audience, and scopes.
- **Configuration ambiguity:** Reject OBO combined with API-key or interactive
  OAuth modes and reject explicit `Authorization` headers when OBO owns that
  header.
- **Compatibility:** Keep old configurations and direct `McpConnection`
  constructors working when new fields and token sources are absent.

## Completion criteria

- All acceptance criteria in `HEADERS-SPEC.md` are met.
- Existing auth, MCP, conversation, and connection-lifecycle behavior remains
  compatible.
- Tests prove correct delegated tokens and contextual headers on concurrent
  shared-connection calls, with no subject-token pass-through or leakage.
- The packaged schema, docs, and example agree on the accepted configuration.
- Header rendering meets the approved performance budget, excluding token
  exchange/network time.
- PR #28 contains only validated implementation changes and remains unmerged.

## Validation record

- MCP configuration, registry, request-header/OBO, JWT, FastAPI, and conversation
  integration tests: 70 passed.
- MCP configuration and performance budget tests: 22 passed, including the
  stdio schema regression and header-rendering p95 budget.
- Token-port, delegated-token, MCP request-header, and registry tests: 31
  passed, including the unchanged credential-free exchange-port signature.
- Ruff checks and format checks passed for the updated configuration and test
  files; `git diff --check` passed.
- The offline MCP example loaded all three configured servers without opening a
  remote connection or requesting an OBO token.
- Draft 2020-12 schema validation passed, including a valid stdio document with
  HTTP-only settings omitted.

# Quickstart Validation Guide: OpenAI and Anthropic Endpoint Exposure

This guide validates feature behavior end-to-end after implementation.

## Prerequisites

- Feature artifacts available in `specs/001-openai-endpoint-exposure/`
- Implementations available for Python, .NET, and Java packages
- Test tooling configured for unit, contract, integration, and parity suites

## References

- Specification: [spec.md](./spec.md)
- Plan: [plan.md](./plan.md)
- Data model: [data-model.md](./data-model.md)
- Contracts:

  - [endpoint-surface-contract.md](./contracts/endpoint-surface-contract.md)
  - [standard-exchange-v1.schema.json](./contracts/standard-exchange-v1.schema.json)
  - [agent-descriptor-v1.schema.json](./contracts/agent-descriptor-v1.schema.json)

## Scenario 1: Endpoint Exposure Activation

1. Configure Chat Completions endpoint exposure for one routeKey using framework-standard configuration.
2. Start service host.
3. Send a valid Chat Completions request.
4. Verify response is endpoint-compliant and mapped from standard exchange output.

Expected outcome:

- Endpoint is reachable.
- Request is normalized.
- Registered handler is invoked.

## Scenario 2: Responses Endpoint Activation

1. Configure Responses endpoint exposure for the same routeKey.
2. Send a valid Responses request.
3. Verify normalization and response mapping.

Expected outcome:

- Equivalent handler behavior across endpoint type variants.

## Scenario 3: Anthropic Messages Endpoint Activation

1. Configure Anthropic Messages endpoint exposure for the same routeKey.
2. Send a valid Anthropic Messages request.
3. Verify normalization and response mapping.

Expected outcome:

- Equivalent handler behavior across OpenAI and Anthropic endpoint families.

## Scenario 4: JWT Authentication Flow

1. Configure JWT authentication mode.
2. Send request with valid JWT.
3. Verify handler receives `authContext.userId` and `authContext.authType=jwt`.
4. Send request with invalid JWT.

Expected outcome:

- Valid token: request proceeds to handler.
- Invalid token: authentication error envelope returned, handler not called.

## Scenario 5: API Key User-Resolution Hook Flow

1. Configure API-key mode and register user-resolution hook.
2. Send request with valid API key.
3. Verify hook resolves user and handler receives `authContext.authType=api_key`.
4. Send request with key that hook cannot resolve.

Expected outcome:

- Resolved user: request proceeds to handler.
- Unresolved user: authentication error envelope returned.

## Scenario 6: Developer-Owned Authorization

1. In handler, implement deny rule for a known user context.
2. Send authenticated request matching deny rule.

Expected outcome:

- Authorization error envelope returned.
- Protected business logic is not executed.

## Scenario 7: Missing Handler Registration

1. Send request for a routeKey with no registered handler.

Expected outcome:

- Structured routing error envelope returned.

## Scenario 8: Streaming Validation Across Endpoint Families

1. Send OpenAI Chat Completions request with stream enabled.
2. Send OpenAI Responses request with stream enabled.
3. Send Anthropic Messages request with stream enabled.
4. Verify chunk/completion/error stream events map to standard stream event contract.

Expected outcome:

- Streaming is supported and compliant for all supported endpoint families.
- Interrupted streams return structured stream failure behavior.

## Scenario 9: Contract and Parity Validation

1. Run contract tests against `standard-exchange-v1.schema.json`.
2. Run parity tests for Python/.NET/Java with same fixtures.

Expected outcome:

- Contract tests pass.
- No unapproved cross-language behavior drift.

## Scenario 10: Namespace Validation

1. Verify Python package root starts with `ygo74`.
2. Verify .NET namespace root starts with `Ygo74`.
3. Verify Java group/package root starts with `ygo74`.

Expected outcome:

- Namespace identity is consistent with the `ygo74` root across all artifacts.

## Scenario 11: Performance Budget Validation

1. Execute runtime overhead benchmarks (normalization + auth + dispatch + mapping).
2. Measure p95 latency excluding user handler execution time.
3. Measure p95 time to first stream event for stream-enabled requests.

Expected outcome:

- Runtime overhead remains within plan budget thresholds.

## Scenario 12: Middleware Pipeline Validation

1. Register at least two middleware components with explicit order.
2. Send a request and verify pre-handler middleware invocation order.
3. Verify post-handler middleware invocation order is reversed.
4. Configure one middleware to short-circuit and verify handler is not executed.
5. Configure one middleware to raise an error and verify structured error envelope mapping.

Expected outcome:

- Middleware pipeline honors deterministic ordering and next-callback chaining.
- Short-circuit behavior is consistent and documented.
- Middleware failures are surfaced with structured error responses.

## Scenario 13: Agent Descriptor Declaration and Validation

1. Declare two agent descriptors through framework-standard configuration, each bound to a registered routeKey.
2. Start the service host and read both descriptors back from the descriptor registry.
3. Declare a third descriptor reusing an existing `agentId` and restart.
4. Declare a descriptor whose `capabilities.streaming` is true while streaming is disabled for its route, and restart.
5. Register a handler with no declared descriptor and restart.

Expected outcome:

- Valid descriptors are registered with documented defaults applied and validate against `agent-descriptor-v1.schema.json`.
- Duplicate `agentId` fails initialization with an error naming the duplicate.
- Contradictory capability claim fails initialization with an error naming the contradiction.
- Handler without a descriptor receives a derived minimal descriptor and remains discoverable.

## Scenario 14: Provider Model Listing and Discovery-to-Invocation Round Trip

1. Request the model list with no provider version header and verify the OpenAI list envelope with one entry per discoverable agent.
2. Request the model list with the Anthropic protocol version header and verify the Anthropic list envelope, display names, and creation timestamps.
3. Request the Anthropic model list with pagination parameters smaller than the catalogue size and verify continuation indicators.
4. Request a single model by identifier in each dialect.
5. Request an unknown model identifier, an unsupported provider version, and out-of-range pagination parameters.
6. Take each identifier returned by the listing and submit it as the `model` field of a Chat Completions, Responses, and Anthropic Messages request.
7. Repeat the listing request several times and compare entry order.

Expected outcome:

- Each dialect returns its own envelope and entry shape, selected by the protocol version header.
- Pagination returns the requested page with correct continuation indicators.
- Non-native capability attributes appear only inside the documented additive extension section.
- Every advertised identifier routes to the advertised agent.
- Invalid requests return structured error envelopes with the expected categories.
- Entry order is identical across repeated requests.

## Scenario 15: A2A Agent Card and Cross-Surface Consistency

1. Declare one descriptor with skills, capabilities, documentation URL, and security schemes.
2. Retrieve the agent card from the well-known discovery location.
3. Retrieve the same agent from the OpenAI and Anthropic single-model endpoints.
4. Compare, field by field, every attribute shared by two or more surfaces.
5. Disable the agent card surface and retrieve the well-known location again.

Expected outcome:

- The card reports the same name, description, version, and capability facts as the provider entries.
- Every declared skill is present in the card skill collection.
- The card streaming flag matches the runtime streaming configuration.
- Advertised security schemes match enforced schemes and contain no secret material.
- Shared attributes are identical across all three surfaces with zero divergences.
- With the card surface disabled, the well-known location returns a structured not-found error while the model endpoints keep working.

## Scenario 16: Discovery Access Control and Visibility

1. Configure discovery as publicly readable and request the model list without credentials.
2. Reconfigure discovery to require authentication and repeat the anonymous request.
3. Repeat with a valid credential.
4. Register a visibility rule that hides one agent from a specific caller, then list models and request the hidden agent directly as that caller.
5. Mark an agent as `hidden` in its descriptor, list models, then invoke it directly by identifier.

Expected outcome:

- Public mode returns the listing without credentials.
- Authenticated mode rejects the anonymous request with a structured authentication error and discloses no agent metadata.
- The visibility rule filters listing entries, and the forbidden agent returns a response indistinguishable from a non-existent agent.
- A `hidden` agent is absent from the listing but remains invocable by identifier.

## Scenario 17: Discovery Performance and Parity

1. Register a catalogue of 100 descriptors.
2. Measure p95 latency of the model listing endpoint and of single-agent lookup.
3. Declare an equivalent descriptor set in Python, .NET, and Java and diff the three discovery payloads for each surface.

Expected outcome:

- Listing responses remain within the plan budget of 20ms p95 for 100 agents; single lookup is O(1) by identifier.
- No unapproved cross-language differences in any discovery payload.

## Implementation Snapshot

- Phase status: Setup, Foundational, US1, US2, US3, US4, US5, US6, US7, and Polish scaffolds are present in repository paths.
- Validation note: Contract JSON checks, integration/parity inventory checks, and performance baseline presence checks completed in current environment.
- CI gate note: Performance baseline policy file is enforced by workflow at `.github/workflows/ci.yml`.
- Discovery amendment (2026-08-16): scenarios 13-17 cover the agent descriptor, provider model listings, the A2A agent card, access control, and discovery performance/parity. These scenarios are not yet implemented; run `/speckit.tasks` to regenerate the task breakdown before implementation.

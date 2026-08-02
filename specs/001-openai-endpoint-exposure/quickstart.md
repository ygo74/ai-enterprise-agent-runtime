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

## Implementation Snapshot

- Phase status: Setup, Foundational, US1, US2, US3, US4, US5, US6, US7, and Polish scaffolds are present in repository paths.
- Validation note: Contract JSON checks, integration/parity inventory checks, and performance baseline presence checks completed in current environment.
- CI gate note: Performance baseline policy file is enforced by workflow at `.github/workflows/ci.yml`.

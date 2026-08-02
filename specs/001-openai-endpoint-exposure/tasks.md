# Tasks: OpenAI and Anthropic Endpoint Exposure

**Input**: Design documents from `/specs/001-openai-endpoint-exposure/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Test tasks are mandatory for this feature per constitution gates.

**Organization**: Tasks are grouped by user story so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unresolved dependencies)
- **[Story]**: User story label (`[US1]`..`[US7]`) mapped to spec stories below

## Story Traceability Mapping (Spec -> Tasks)

- **US1** -> Spec User Story 1 (Expose OpenAI and Anthropic Compatible Endpoints)
- **US2** -> Spec User Story 1b (Stream Responses Across Endpoint Families)
- **US3** -> Spec User Story 2 (Configure With Native Framework Patterns)
- **US4** -> Spec User Story 3 (Standard Exchange Format for Use Case Logic)
- **US5** -> Spec User Story 4 (Decoupled Dispatch Pipeline)
- **US6** -> Spec User Story 4b (Middleware Chain)
- **US7** -> Spec User Story 5 (Authentication Context and Developer-Owned Authorization)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the multi-language workspace skeleton, examples skeleton, and baseline project wiring.

- [ ] T001 Create multi-language package structure in packages/python/ygo74/agent_runtime/, packages/dotnet/Ygo74.AgentRuntime/, and packages/java/ygo74-agent-runtime/
- [ ] T002 Initialize Python package metadata and dependency baseline in packages/python/pyproject.toml
- [ ] T003 Initialize .NET solution and project baseline in packages/dotnet/Ygo74.AgentRuntime.sln and packages/dotnet/Ygo74.AgentRuntime/Ygo74.AgentRuntime.csproj
- [ ] T004 Initialize Java project baseline in packages/java/ygo74-agent-runtime/build.gradle
- [ ] T005 Create shared test folder structure in tests/contract/, tests/integration/, tests/parity/, and tests/performance/
- [ ] T006 Create usage example folders in docs/examples/dotnet-agentframework/, docs/examples/python-langchain-fastapi/, and docs/examples/java-springai-springboot/
- [ ] T007 Record reuse-first inventory targets in specs/001-openai-endpoint-exposure/research.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build shared contracts, core abstractions, observability, and domain organization required by all stories.

**CRITICAL**: No user story work starts before this phase is complete.

- [ ] T008 Implement Python core exchange models in packages/python/ygo74/agent_runtime/domains/contracts/exchange_models.py
- [ ] T009 [P] Implement .NET core exchange models in packages/dotnet/Ygo74.AgentRuntime/Domains/Contracts/ExchangeModels.cs
- [ ] T010 [P] Implement Java core exchange models in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/contracts/ExchangeModels.java
- [ ] T011 Implement Python error envelope contract in packages/python/ygo74/agent_runtime/domains/contracts/error_envelope.py
- [ ] T012 [P] Implement .NET error envelope contract in packages/dotnet/Ygo74.AgentRuntime/Domains/Contracts/ErrorEnvelope.cs
- [ ] T013 [P] Implement Java error envelope contract in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/contracts/ErrorEnvelope.java
- [ ] T014 Implement Python dispatcher abstractions in packages/python/ygo74/agent_runtime/routing/dispatcher.py
- [ ] T015 [P] Implement .NET dispatcher abstractions in packages/dotnet/Ygo74.AgentRuntime/Routing/IDispatcher.cs
- [ ] T016 [P] Implement Java dispatcher abstractions in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/routing/Dispatcher.java
- [ ] T017 Implement Python middleware interfaces in packages/python/ygo74/agent_runtime/middleware/interfaces.py
- [ ] T018 [P] Implement .NET middleware interfaces in packages/dotnet/Ygo74.AgentRuntime/Middleware/IMiddleware.cs
- [ ] T019 [P] Implement Java middleware interfaces in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/middleware/Middleware.java
- [ ] T020 Configure Python standard logging and level routing in packages/python/ygo74/agent_runtime/observability/logging_config.py
- [ ] T021 [P] Configure .NET standard logging and level routing in packages/dotnet/Ygo74.AgentRuntime/Observability/LoggingSetup.cs
- [ ] T022 [P] Configure Java standard logging and level routing in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/observability/LoggingSetup.java
- [ ] T023 Add OpenTelemetry sink wiring hooks in packages/python/ygo74/agent_runtime/observability/otel.py
- [ ] T024 [P] Add OpenTelemetry sink wiring hooks in packages/dotnet/Ygo74.AgentRuntime/Observability/OpenTelemetrySetup.cs
- [ ] T025 [P] Add OpenTelemetry sink wiring hooks in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/observability/OpenTelemetrySetup.java
- [ ] T026 Add domain-oriented public API entry points in packages/python/ygo74/agent_runtime/\_\_init\_\_.py, packages/dotnet/Ygo74.AgentRuntime/PublicApi.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/PublicApi.java

**Checkpoint**: Foundation complete, story implementation can start.

---

## Phase 3: User Story 1 - Expose OpenAI and Anthropic Endpoints (Priority: P1) MVP

**Goal**: Expose OpenAI Chat Completions/Responses and Anthropic Messages in non-streaming mode.

**Independent Test**: Requests to each endpoint family are normalized and return compliant responses.

### Tests for User Story 1

- [ ] T027 [P] [US1] Add non-stream endpoint contract tests in tests/contract/test_endpoint_surface_non_stream.json
- [ ] T028 [P] [US1] Add Python non-stream integration tests in tests/integration/python/test_non_stream_endpoints.py
- [ ] T029 [P] [US1] Add .NET non-stream integration tests in tests/integration/dotnet/NonStreamEndpointsTests.cs
- [ ] T030 [P] [US1] Add Java non-stream integration tests in tests/integration/java/NonStreamEndpointsTest.java
- [ ] T112 [P] [US1] Add endpoint metadata preservation tests for request_id, model_id, and context fields in tests/integration/python/test_metadata_preservation.py, tests/integration/dotnet/MetadataPreservationTests.cs, and tests/integration/java/MetadataPreservationTest.java

### Implementation for User Story 1

- [ ] T031 [US1] Implement Python OpenAI and Anthropic endpoint adapters in packages/python/ygo74/agent_runtime/domains/endpoints/adapters.py
- [ ] T032 [P] [US1] Implement .NET OpenAI and Anthropic endpoint adapters in packages/dotnet/Ygo74.AgentRuntime/Domains/Endpoints/EndpointAdapters.cs
- [ ] T033 [P] [US1] Implement Java OpenAI and Anthropic endpoint adapters in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/endpoints/EndpointAdapters.java
- [ ] T034 [US1] Implement Python endpoint-to-exchange normalization in packages/python/ygo74/agent_runtime/domains/mapping/request_mapper.py
- [ ] T035 [P] [US1] Implement .NET endpoint-to-exchange normalization in packages/dotnet/Ygo74.AgentRuntime/Domains/Mapping/RequestMapper.cs
- [ ] T036 [P] [US1] Implement Java endpoint-to-exchange normalization in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/mapping/RequestMapper.java
- [ ] T037 [US1] Implement exchange-to-endpoint response mapping in packages/python/ygo74/agent_runtime/domains/mapping/response_mapper.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Mapping/ResponseMapper.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/mapping/ResponseMapper.java

**Checkpoint**: Non-streaming endpoint exposure works for all endpoint families.

---

## Phase 4: User Story 2 - Streaming Across Endpoint Families (Priority: P1)

**Goal**: Support compliant streaming for OpenAI Chat/Responses and Anthropic Messages.

**Independent Test**: Stream chunks/events are emitted and terminated correctly for all families.

### Tests for User Story 2

- [ ] T038 [P] [US2] Add streaming contract tests in tests/contract/test_endpoint_surface_streaming.json
- [ ] T039 [P] [US2] Add Python streaming integration tests in tests/integration/python/test_streaming_endpoints.py
- [ ] T040 [P] [US2] Add .NET streaming integration tests in tests/integration/dotnet/StreamingEndpointsTests.cs
- [ ] T041 [P] [US2] Add Java streaming integration tests in tests/integration/java/StreamingEndpointsTest.java
- [ ] T042 [P] [US2] Add interrupted-stream behavior tests in tests/integration/python/test_interrupted_streams.py, tests/integration/dotnet/InterruptedStreamsTests.cs, and tests/integration/java/InterruptedStreamsTest.java

### Implementation for User Story 2

- [ ] T043 [US2] Implement Python streaming event contract support in packages/python/ygo74/agent_runtime/domains/contracts/stream_events.py
- [ ] T044 [P] [US2] Implement .NET streaming event contract support in packages/dotnet/Ygo74.AgentRuntime/Domains/Contracts/StreamingEvent.cs
- [ ] T045 [P] [US2] Implement Java streaming event contract support in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/contracts/StreamingEvent.java
- [ ] T046 [US2] Implement OpenAI streaming transport mapping in packages/python/ygo74/agent_runtime/domains/streaming/openai_stream_mapper.py and packages/dotnet/Ygo74.AgentRuntime/Domains/Streaming/OpenAiStreamMapper.cs
- [ ] T047 [P] [US2] Implement Anthropic streaming transport mapping in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/streaming/AnthropicStreamMapper.java
- [ ] T048 [US2] Implement stream completion and error termination handling in packages/python/ygo74/agent_runtime/domains/streaming/stream_termination.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Streaming/StreamTermination.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/streaming/StreamTermination.java

**Checkpoint**: Streaming behavior is available and compliant across endpoint families.

---

## Phase 5: User Story 3 - Native Framework Configuration (Priority: P2)

**Goal**: Configure endpoints through idiomatic framework mechanisms in each language.

**Independent Test**: Endpoint activation works from native config without custom bootstrap.

### Tests for User Story 3

- [ ] T049 [P] [US3] Add configuration validation tests in tests/contract/test_configuration_rules.json
- [ ] T050 [P] [US3] Add Python FastAPI config binding tests in tests/integration/python/test_fastapi_config.py
- [ ] T051 [P] [US3] Add .NET options binding tests in tests/integration/dotnet/OptionsBindingTests.cs
- [ ] T052 [P] [US3] Add Java Spring Boot config binding tests in tests/integration/java/ConfigurationBindingTest.java

### Implementation for User Story 3

- [ ] T053 [US3] Implement Python configuration models and validation in packages/python/ygo74/agent_runtime/domains/configuration/models.py
- [ ] T054 [P] [US3] Implement .NET configuration models and validation in packages/dotnet/Ygo74.AgentRuntime/Domains/Configuration/EndpointOptions.cs
- [ ] T055 [P] [US3] Implement Java configuration models and validation in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/configuration/EndpointProperties.java
- [ ] T056 [US3] Implement endpoint startup validation guards in packages/python/ygo74/agent_runtime/domains/configuration/validator.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Configuration/EndpointOptionsValidator.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/configuration/EndpointPropertiesValidator.java
- [ ] T057 [US3] Document native configuration examples in docs/examples/python-langchain-fastapi/configuration.md, docs/examples/dotnet-agentframework/configuration.md, and docs/examples/java-springai-springboot/configuration.md

**Checkpoint**: Native framework configuration is complete and validated.

---

## Phase 6: User Story 4 - Standard Exchange Handler Contract (Priority: P3)

**Goal**: Developers process a single standard request/response contract independent of endpoint wire format.

**Independent Test**: Same handler logic works for all supported endpoint families via standard exchange objects.

### Tests for User Story 4

- [ ] T058 [P] [US4] Add standard exchange schema conformance tests in tests/contract/test_standard_exchange_schema.py
- [ ] T059 [P] [US4] Add parity fixture tests for exchange mapping in tests/parity/test_exchange_parity.py
- [ ] T060 [P] [US4] Add handler contract tests in tests/integration/python/test_handler_contract.py, tests/integration/dotnet/HandlerContractTests.cs, and tests/integration/java/HandlerContractTest.java

### Implementation for User Story 4

- [ ] T061 [US4] Implement Python handler interface for standard exchange in packages/python/ygo74/agent_runtime/domains/handlers/handler_protocol.py
- [ ] T062 [P] [US4] Implement .NET handler interface for standard exchange in packages/dotnet/Ygo74.AgentRuntime/Domains/Handlers/IUseCaseHandler.cs
- [ ] T063 [P] [US4] Implement Java handler interface for standard exchange in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/handlers/UseCaseHandler.java
- [ ] T064 [US4] Implement handler response validation in packages/python/ygo74/agent_runtime/domains/handlers/response_validator.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Handlers/ResponseValidator.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/handlers/ResponseValidator.java
- [ ] T065 [US4] Provide minimal runnable handler examples in docs/examples/python-langchain-fastapi/handlers/basic_handler.py, docs/examples/dotnet-agentframework/Handlers/BasicHandler.cs, and docs/examples/java-springai-springboot/src/main/java/com/ygo74/examples/BasicHandler.java

**Checkpoint**: Standard exchange contract is stable and usable by developers.

---

## Phase 7: User Story 5 - Decoupled Routing and Dispatch (Priority: P1)

**Goal**: Route standardized messages to registered handlers with deterministic behavior.

**Independent Test**: Route keys resolve to handlers; missing handlers return structured routing errors.

### Tests for User Story 5

- [ ] T066 [P] [US5] Add route registration contract tests in tests/contract/test_handler_registration_rules.json
- [ ] T067 [P] [US5] Add Python dispatch routing tests in tests/integration/python/test_dispatch_routing.py
- [ ] T068 [P] [US5] Add .NET dispatch routing tests in tests/integration/dotnet/DispatchRoutingTests.cs
- [ ] T069 [P] [US5] Add Java dispatch routing tests in tests/integration/java/DispatchRoutingTest.java

### Implementation for User Story 5

- [ ] T070 [US5] Implement Python route registry in packages/python/ygo74/agent_runtime/routing/route_registry.py
- [ ] T071 [P] [US5] Implement .NET route registry in packages/dotnet/Ygo74.AgentRuntime/Routing/RouteRegistry.cs
- [ ] T072 [P] [US5] Implement Java route registry in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/routing/RouteRegistry.java
- [ ] T073 [US5] Implement deterministic dispatcher execution in packages/python/ygo74/agent_runtime/routing/dispatcher_impl.py, packages/dotnet/Ygo74.AgentRuntime/Routing/Dispatcher.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/routing/DispatcherImpl.java
- [ ] T074 [US5] Implement structured routing error mapping in packages/python/ygo74/agent_runtime/routing/routing_errors.py, packages/dotnet/Ygo74.AgentRuntime/Routing/RoutingErrors.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/routing/RoutingErrors.java

**Checkpoint**: Decoupled routing/dispatch is complete.

---

## Phase 8: User Story 6 - Middleware Chain (Priority: P1)

**Goal**: Provide ordered pre/post middleware pipeline with next-callback and short-circuit support.

**Independent Test**: Middleware chain order, response post-processing, short-circuit, and failure handling are deterministic.

### Tests for User Story 6

- [ ] T075 [P] [US6] Add middleware contract tests in tests/contract/test_middleware_pipeline_contract.json
- [ ] T076 [P] [US6] Add Python middleware chain tests in tests/integration/python/test_middleware_pipeline.py
- [ ] T077 [P] [US6] Add .NET middleware chain tests in tests/integration/dotnet/MiddlewarePipelineTests.cs
- [ ] T078 [P] [US6] Add Java middleware chain tests in tests/integration/java/MiddlewarePipelineTest.java
- [ ] T079 [P] [US6] Add middleware short-circuit and failure tests in tests/integration/python/test_middleware_short_circuit.py, tests/integration/dotnet/MiddlewareShortCircuitTests.cs, and tests/integration/java/MiddlewareShortCircuitTest.java

### Implementation for User Story 6

- [ ] T080 [US6] Implement Python middleware registration and ordering in packages/python/ygo74/agent_runtime/middleware/registry.py
- [ ] T081 [P] [US6] Implement .NET middleware registration and ordering in packages/dotnet/Ygo74.AgentRuntime/Middleware/MiddlewareRegistry.cs
- [ ] T082 [P] [US6] Implement Java middleware registration and ordering in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/middleware/MiddlewareRegistry.java
- [ ] T083 [US6] Implement Python middleware pipeline executor with next-callback in packages/python/ygo74/agent_runtime/middleware/pipeline.py
- [ ] T084 [P] [US6] Implement .NET middleware pipeline executor with next-callback in packages/dotnet/Ygo74.AgentRuntime/Middleware/MiddlewarePipeline.cs
- [ ] T085 [P] [US6] Implement Java middleware pipeline executor with next-callback in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/middleware/MiddlewarePipeline.java
- [ ] T086 [US6] Implement middleware error-to-envelope mapping in packages/python/ygo74/agent_runtime/middleware/middleware_errors.py, packages/dotnet/Ygo74.AgentRuntime/Middleware/MiddlewareErrors.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/middleware/MiddlewareErrors.java

**Checkpoint**: Middleware pipeline works with deterministic chain semantics.

---

## Phase 9: User Story 7 - Shared Authentication Context and Developer Authorization (Priority: P1)

**Goal**: Runtime handles JWT/API-key user context; developers enforce authorization in their handlers.

**Independent Test**: Valid auth produces user context, developer deny rules block business execution.

### Tests for User Story 7

- [ ] T087 [P] [US7] Add JWT and API-key auth contract tests in tests/contract/test_auth_context_contract.json
- [ ] T088 [P] [US7] Add Python auth context integration tests in tests/integration/python/test_auth_context.py
- [ ] T089 [P] [US7] Add .NET auth context integration tests in tests/integration/dotnet/AuthContextTests.cs
- [ ] T090 [P] [US7] Add Java auth context integration tests in tests/integration/java/AuthContextTest.java
- [ ] T091 [P] [US7] Add developer-owned authorization denial tests in tests/integration/python/test_authorization_denial.py, tests/integration/dotnet/AuthorizationDenialTests.cs, and tests/integration/java/AuthorizationDenialTest.java

### Implementation for User Story 7

- [ ] T092 [US7] Implement Python JWT authentication and user projection in packages/python/ygo74/agent_runtime/domains/auth/jwt_authenticator.py
- [ ] T093 [P] [US7] Implement .NET JWT authentication and user projection in packages/dotnet/Ygo74.AgentRuntime/Domains/Auth/JwtAuthenticator.cs
- [ ] T094 [P] [US7] Implement Java JWT authentication and user projection in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/auth/JwtAuthenticator.java
- [ ] T095 [US7] Implement Python API-key user-resolution hook integration in packages/python/ygo74/agent_runtime/domains/auth/apikey_authenticator.py
- [ ] T096 [P] [US7] Implement .NET API-key user-resolution hook integration in packages/dotnet/Ygo74.AgentRuntime/Domains/Auth/ApiKeyAuthenticator.cs
- [ ] T097 [P] [US7] Implement Java API-key user-resolution hook integration in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/auth/ApiKeyAuthenticator.java
- [ ] T098 [US7] Implement structured auth/authz error mapping in packages/python/ygo74/agent_runtime/domains/auth/auth_errors.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Auth/AuthErrors.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/auth/AuthErrors.java
- [ ] T099 [US7] Document developer-owned authorization extension points in docs/examples/python-langchain-fastapi/authorization.md, docs/examples/dotnet-agentframework/authorization.md, and docs/examples/java-springai-springboot/authorization.md

**Checkpoint**: Shared authentication and developer-owned authorization are complete.

---

## Phase 10: Polish and Cross-Cutting Concerns

**Purpose**: Final hardening, examples validation, observability validation, and end-to-end quality gates.

- [ ] T100 [P] Validate log level/sink reconfiguration and OpenTelemetry redirection in tests/integration/python/test_observability_reconfiguration.py, tests/integration/dotnet/ObservabilityReconfigurationTests.cs, and tests/integration/java/ObservabilityReconfigurationTest.java
- [ ] T101 [P] Validate domain discoverability in public API docs at docs/examples/README.md
- [ ] T102 [P] Validate runnable examples execute end-to-end in docs/examples/dotnet-agentframework/, docs/examples/python-langchain-fastapi/, and docs/examples/java-springai-springboot/
- [ ] T103 Run full contract suite in tests/contract/
- [ ] T104 Run full integration suite in tests/integration/
- [ ] T105 Run full parity suite in tests/parity/
- [ ] T106 Execute quickstart verification steps in specs/001-openai-endpoint-exposure/quickstart.md
- [ ] T107 Final documentation update for feature behavior in specs/001-openai-endpoint-exposure/quickstart.md
- [ ] T108 [P] Add cross-language namespace identity conformance tests in tests/parity/test_namespace_identity.py, tests/integration/dotnet/NamespaceIdentityTests.cs, and tests/integration/java/NamespaceIdentityTest.java
- [ ] T109 [P] Add cross-language performance budget tests for dispatch and streaming first-event latency in tests/performance/python/test_performance_budget.py, tests/performance/dotnet/PerformanceBudgetTests.cs, and tests/performance/java/PerformanceBudgetTest.java
- [ ] T110 [P] Add performance threshold baselines and regression policy in tests/performance/baselines/performance_thresholds.json
- [ ] T111 Enforce performance regression gate execution in .github/workflows/ci.yml

---

## Dependencies and Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies.
- Foundational (Phase 2): depends on Setup and blocks all user stories.
- User Stories (Phases 3-9): depend on Foundational.
- Polish (Phase 10): depends on completed target user stories.

### User Story Dependencies

- **US1** (Endpoints non-stream): starts after Foundational.
- **US2** (Streaming): depends on US1 endpoint adapters and mappers.
- **US3** (Native configuration): starts after Foundational; integrates with US1/US2.
- **US4** (Standard exchange handler): starts after Foundational; integrates with US1.
- **US5** (Routing/dispatch): starts after Foundational; depends on US4 handler contracts.
- **US6** (Middleware chain): starts after Foundational; depends on US5 dispatcher core.
- **US7** (Auth context + authz): starts after Foundational; integrates with US5/US6 pipeline.

### Within Each User Story

- Tests are written first and must fail before implementation.
- Contracts and interfaces before concrete adapters.
- Core behavior before docs/examples updates.

---

## Parallel Opportunities

- Phase 1 tasks T002-T004 can run in parallel after T001.
- Foundational language-specific tasks marked [P] can run in parallel.
- For each story, Python/.NET/Java implementation tasks marked [P] can run in parallel.
- Contract, integration, and parity tests marked [P] can run in parallel per story.

---

## Parallel Examples by Story

### US1

- Run in parallel:
  - T028, T029, T030
  - T032, T033, T035, T036

### US2

- Run in parallel:
  - T039, T040, T041
  - T044, T045, T047

### US3

- Run in parallel:
  - T050, T051, T052
  - T054, T055

### US4

- Run in parallel:
  - T059, T060
  - T062, T063

### US5

- Run in parallel:
  - T067, T068, T069
  - T071, T072

### US6

- Run in parallel:
  - T076, T077, T078
  - T081, T082, T084, T085

### US7

- Run in parallel:
  - T088, T089, T090, T091
  - T093, T094, T096, T097

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Deliver Phase 3 (US1) as first MVP.
3. Validate US1 independently before expanding scope.

### Incremental Delivery

1. Add US2 (streaming) and US3 (native config).
2. Add US4 and US5 for robust handler and routing architecture.
3. Add US6 middleware chain and US7 auth context/authorization pattern.
4. Finish with Phase 10 quality and readiness checks.

### Multi-Developer Strategy

1. Team A: Python track tasks for active phase.
2. Team B: .NET track tasks for active phase.
3. Team C: Java track tasks for active phase.
4. Shared QA: contract/parity tests and cross-language examples.

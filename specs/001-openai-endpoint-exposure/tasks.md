# Tasks: OpenAI and Anthropic Endpoint Exposure

**Input**: Design documents from `/specs/001-openai-endpoint-exposure/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Test tasks are mandatory for this feature per constitution gates.

**Organization**: Tasks are grouped by user story so each story is independently implementable and testable.

**Revision**: 2026-08-16 amendment adds the agent capability discovery phases (Phase 11-16,
tasks T113-T188) covering FR-024..FR-046 and SC-014..SC-019. Phases 1-10 were delivered
before this amendment and are retained as completed history.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unresolved dependencies)
- **[Story]**: User story label (`[US1]`..`[US11]`) mapped to spec stories below

## Story Traceability Mapping (Spec -> Tasks)

- **US1** -> Spec User Story 1 (Expose OpenAI and Anthropic Compatible Endpoints)
- **US2** -> Spec User Story 1b (Stream Responses Across Endpoint Families)
- **US3** -> Spec User Story 2 (Configure With Native Framework Patterns)
- **US4** -> Spec User Story 3 (Standard Exchange Format for Use Case Logic)
- **US5** -> Spec User Story 4 (Decoupled Dispatch Pipeline)
- **US6** -> Spec User Story 4b (Middleware Chain)
- **US7** -> Spec User Story 5 (Authentication Context and Developer-Owned Authorization)
- **US8** -> Spec User Story 6 (Declare Agent Identity and Capabilities From a Single Source)
- **US9** -> Spec User Story 6b (Discover Agents Through Provider-Compatible Model Endpoints)
- **US10** -> Spec User Story 6c (Serve an A2A-Ready Agent Card From the Same Descriptor)
- **US11** -> Spec User Story 6d (Control Discovery Access and Visibility)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the multi-language workspace skeleton, examples skeleton, and baseline project wiring.

- [X] T001 Create multi-language package structure in packages/python/ygo74/agent_runtime/, packages/dotnet/Ygo74.AgentRuntime/, and packages/java/ygo74-agent-runtime/
- [X] T002 Initialize Python package metadata and dependency baseline in packages/python/pyproject.toml
- [X] T003 Initialize .NET solution and project baseline in packages/dotnet/Ygo74.AgentRuntime.sln and packages/dotnet/Ygo74.AgentRuntime/Ygo74.AgentRuntime.csproj
- [X] T004 Initialize Java project baseline in packages/java/ygo74-agent-runtime/build.gradle
- [X] T005 Create shared test folder structure in tests/contract/, tests/integration/, tests/parity/, and tests/performance/
- [X] T006 Create usage example folders in docs/examples/dotnet-agentframework/, docs/examples/python-langchain-fastapi/, and docs/examples/java-springai-springboot/
- [X] T007 Record reuse-first inventory targets in specs/001-openai-endpoint-exposure/research.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build shared contracts, core abstractions, observability, and domain organization required by all stories.

**CRITICAL**: No user story work starts before this phase is complete.

- [X] T008 Implement Python core exchange models in packages/python/ygo74/agent_runtime/domains/contracts/exchange_models.py
- [X] T009 [P] Implement .NET core exchange models in packages/dotnet/Ygo74.AgentRuntime/Domains/Contracts/ExchangeModels.cs
- [X] T010 [P] Implement Java core exchange models in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/contracts/ExchangeModels.java
- [X] T011 Implement Python error envelope contract in packages/python/ygo74/agent_runtime/domains/contracts/error_envelope.py
- [X] T012 [P] Implement .NET error envelope contract in packages/dotnet/Ygo74.AgentRuntime/Domains/Contracts/ErrorEnvelope.cs
- [X] T013 [P] Implement Java error envelope contract in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/contracts/ErrorEnvelope.java
- [X] T014 Implement Python dispatcher abstractions in packages/python/ygo74/agent_runtime/routing/dispatcher.py
- [X] T015 [P] Implement .NET dispatcher abstractions in packages/dotnet/Ygo74.AgentRuntime/Routing/IDispatcher.cs
- [X] T016 [P] Implement Java dispatcher abstractions in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/routing/Dispatcher.java
- [X] T017 Implement Python middleware interfaces in packages/python/ygo74/agent_runtime/middleware/interfaces.py
- [X] T018 [P] Implement .NET middleware interfaces in packages/dotnet/Ygo74.AgentRuntime/Middleware/IMiddleware.cs
- [X] T019 [P] Implement Java middleware interfaces in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/middleware/Middleware.java
- [X] T020 Configure Python standard logging and level routing in packages/python/ygo74/agent_runtime/observability/logging_config.py
- [X] T021 [P] Configure .NET standard logging and level routing in packages/dotnet/Ygo74.AgentRuntime/Observability/LoggingSetup.cs
- [X] T022 [P] Configure Java standard logging and level routing in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/observability/LoggingSetup.java
- [X] T023 Add OpenTelemetry sink wiring hooks in packages/python/ygo74/agent_runtime/observability/otel.py
- [X] T024 [P] Add OpenTelemetry sink wiring hooks in packages/dotnet/Ygo74.AgentRuntime/Observability/OpenTelemetrySetup.cs
- [X] T025 [P] Add OpenTelemetry sink wiring hooks in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/observability/OpenTelemetrySetup.java
- [X] T026 Add domain-oriented public API entry points in packages/python/ygo74/agent_runtime/\_\_init\_\_.py, packages/dotnet/Ygo74.AgentRuntime/PublicApi.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/PublicApi.java

**Checkpoint**: Foundation complete, story implementation can start.

---

## Phase 3: User Story 1 - Expose OpenAI and Anthropic Endpoints (Priority: P1) MVP

**Goal**: Expose OpenAI Chat Completions/Responses and Anthropic Messages in non-streaming mode.

**Independent Test**: Requests to each endpoint family are normalized and return compliant responses.

### Tests for User Story 1

- [X] T027 [P] [US1] Add non-stream endpoint contract tests in tests/contract/test_endpoint_surface_non_stream.json
- [X] T028 [P] [US1] Add Python non-stream integration tests in tests/integration/python/test_non_stream_endpoints.py
- [X] T029 [P] [US1] Add .NET non-stream integration tests in tests/integration/dotnet/NonStreamEndpointsTests.cs
- [X] T030 [P] [US1] Add Java non-stream integration tests in tests/integration/java/NonStreamEndpointsTest.java
- [X] T112 [P] [US1] Add endpoint metadata preservation tests for request_id, model_id, and context fields in tests/integration/python/test_metadata_preservation.py, tests/integration/dotnet/MetadataPreservationTests.cs, and tests/integration/java/MetadataPreservationTest.java

### Implementation for User Story 1

- [X] T031 [US1] Implement Python OpenAI and Anthropic endpoint adapters in packages/python/ygo74/agent_runtime/domains/endpoints/adapters.py
- [X] T032 [P] [US1] Implement .NET OpenAI and Anthropic endpoint adapters in packages/dotnet/Ygo74.AgentRuntime/Domains/Endpoints/EndpointAdapters.cs
- [X] T033 [P] [US1] Implement Java OpenAI and Anthropic endpoint adapters in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/endpoints/EndpointAdapters.java
- [X] T034 [US1] Implement Python endpoint-to-exchange normalization in packages/python/ygo74/agent_runtime/domains/mapping/request_mapper.py
- [X] T035 [P] [US1] Implement .NET endpoint-to-exchange normalization in packages/dotnet/Ygo74.AgentRuntime/Domains/Mapping/RequestMapper.cs
- [X] T036 [P] [US1] Implement Java endpoint-to-exchange normalization in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/mapping/RequestMapper.java
- [X] T037 [US1] Implement exchange-to-endpoint response mapping in packages/python/ygo74/agent_runtime/domains/mapping/response_mapper.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Mapping/ResponseMapper.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/mapping/ResponseMapper.java

**Checkpoint**: Non-streaming endpoint exposure works for all endpoint families.

---

## Phase 4: User Story 2 - Streaming Across Endpoint Families (Priority: P1)

**Goal**: Support compliant streaming for OpenAI Chat/Responses and Anthropic Messages.

**Independent Test**: Stream chunks/events are emitted and terminated correctly for all families.

### Tests for User Story 2

- [X] T038 [P] [US2] Add streaming contract tests in tests/contract/test_endpoint_surface_streaming.json
- [X] T039 [P] [US2] Add Python streaming integration tests in tests/integration/python/test_streaming_endpoints.py
- [X] T040 [P] [US2] Add .NET streaming integration tests in tests/integration/dotnet/StreamingEndpointsTests.cs
- [X] T041 [P] [US2] Add Java streaming integration tests in tests/integration/java/StreamingEndpointsTest.java
- [X] T042 [P] [US2] Add interrupted-stream behavior tests in tests/integration/python/test_interrupted_streams.py, tests/integration/dotnet/InterruptedStreamsTests.cs, and tests/integration/java/InterruptedStreamsTest.java

### Implementation for User Story 2

- [X] T043 [US2] Implement Python streaming event contract support in packages/python/ygo74/agent_runtime/domains/contracts/stream_events.py
- [X] T044 [P] [US2] Implement .NET streaming event contract support in packages/dotnet/Ygo74.AgentRuntime/Domains/Contracts/StreamingEvent.cs
- [X] T045 [P] [US2] Implement Java streaming event contract support in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/contracts/StreamingEvent.java
- [X] T046 [US2] Implement OpenAI streaming transport mapping in packages/python/ygo74/agent_runtime/domains/streaming/openai_stream_mapper.py and packages/dotnet/Ygo74.AgentRuntime/Domains/Streaming/OpenAiStreamMapper.cs
- [X] T047 [P] [US2] Implement Anthropic streaming transport mapping in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/streaming/AnthropicStreamMapper.java
- [X] T048 [US2] Implement stream completion and error termination handling in packages/python/ygo74/agent_runtime/domains/streaming/stream_termination.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Streaming/StreamTermination.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/streaming/StreamTermination.java

**Checkpoint**: Streaming behavior is available and compliant across endpoint families.

---

## Phase 5: User Story 3 - Native Framework Configuration (Priority: P2)

**Goal**: Configure endpoints through idiomatic framework mechanisms in each language.

**Independent Test**: Endpoint activation works from native config without custom bootstrap.

### Tests for User Story 3

- [X] T049 [P] [US3] Add configuration validation tests in tests/contract/test_configuration_rules.json
- [X] T050 [P] [US3] Add Python FastAPI config binding tests in tests/integration/python/test_fastapi_config.py
- [X] T051 [P] [US3] Add .NET options binding tests in tests/integration/dotnet/OptionsBindingTests.cs
- [X] T052 [P] [US3] Add Java Spring Boot config binding tests in tests/integration/java/ConfigurationBindingTest.java

### Implementation for User Story 3

- [X] T053 [US3] Implement Python configuration models and validation in packages/python/ygo74/agent_runtime/domains/configuration/models.py
- [X] T054 [P] [US3] Implement .NET configuration models and validation in packages/dotnet/Ygo74.AgentRuntime/Domains/Configuration/EndpointOptions.cs
- [X] T055 [P] [US3] Implement Java configuration models and validation in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/configuration/EndpointProperties.java
- [X] T056 [US3] Implement endpoint startup validation guards in packages/python/ygo74/agent_runtime/domains/configuration/validator.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Configuration/EndpointOptionsValidator.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/configuration/EndpointPropertiesValidator.java
- [X] T057 [US3] Document native configuration examples in docs/examples/python-langchain-fastapi/configuration.md, docs/examples/dotnet-agentframework/configuration.md, and docs/examples/java-springai-springboot/configuration.md

**Checkpoint**: Native framework configuration is complete and validated.

---

## Phase 6: User Story 4 - Standard Exchange Handler Contract (Priority: P3)

**Goal**: Developers process a single standard request/response contract independent of endpoint wire format.

**Independent Test**: Same handler logic works for all supported endpoint families via standard exchange objects.

### Tests for User Story 4

- [X] T058 [P] [US4] Add standard exchange schema conformance tests in tests/contract/test_standard_exchange_schema.py
- [X] T059 [P] [US4] Add parity fixture tests for exchange mapping in tests/parity/test_exchange_parity.py
- [X] T060 [P] [US4] Add handler contract tests in tests/integration/python/test_handler_contract.py, tests/integration/dotnet/HandlerContractTests.cs, and tests/integration/java/HandlerContractTest.java

### Implementation for User Story 4

- [X] T061 [US4] Implement Python handler interface for standard exchange in packages/python/ygo74/agent_runtime/domains/handlers/handler_protocol.py
- [X] T062 [P] [US4] Implement .NET handler interface for standard exchange in packages/dotnet/Ygo74.AgentRuntime/Domains/Handlers/IUseCaseHandler.cs
- [X] T063 [P] [US4] Implement Java handler interface for standard exchange in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/handlers/UseCaseHandler.java
- [X] T064 [US4] Implement handler response validation in packages/python/ygo74/agent_runtime/domains/handlers/response_validator.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Handlers/ResponseValidator.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/handlers/ResponseValidator.java
- [X] T065 [US4] Provide minimal runnable handler examples in docs/examples/python-langchain-fastapi/handlers/basic_handler.py, docs/examples/dotnet-agentframework/Handlers/BasicHandler.cs, and docs/examples/java-springai-springboot/src/main/java/com/ygo74/examples/BasicHandler.java

**Checkpoint**: Standard exchange contract is stable and usable by developers.

---

## Phase 7: User Story 5 - Decoupled Routing and Dispatch (Priority: P1)

**Goal**: Route standardized messages to registered handlers with deterministic behavior.

**Independent Test**: Route keys resolve to handlers; missing handlers return structured routing errors.

### Tests for User Story 5

- [X] T066 [P] [US5] Add route registration contract tests in tests/contract/test_handler_registration_rules.json
- [X] T067 [P] [US5] Add Python dispatch routing tests in tests/integration/python/test_dispatch_routing.py
- [X] T068 [P] [US5] Add .NET dispatch routing tests in tests/integration/dotnet/DispatchRoutingTests.cs
- [X] T069 [P] [US5] Add Java dispatch routing tests in tests/integration/java/DispatchRoutingTest.java

### Implementation for User Story 5

- [X] T070 [US5] Implement Python route registry in packages/python/ygo74/agent_runtime/routing/route_registry.py
- [X] T071 [P] [US5] Implement .NET route registry in packages/dotnet/Ygo74.AgentRuntime/Routing/RouteRegistry.cs
- [X] T072 [P] [US5] Implement Java route registry in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/routing/RouteRegistry.java
- [X] T073 [US5] Implement deterministic dispatcher execution in packages/python/ygo74/agent_runtime/routing/dispatcher_impl.py, packages/dotnet/Ygo74.AgentRuntime/Routing/Dispatcher.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/routing/DispatcherImpl.java
- [X] T074 [US5] Implement structured routing error mapping in packages/python/ygo74/agent_runtime/routing/routing_errors.py, packages/dotnet/Ygo74.AgentRuntime/Routing/RoutingErrors.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/routing/RoutingErrors.java

**Checkpoint**: Decoupled routing/dispatch is complete.

---

## Phase 8: User Story 6 - Middleware Chain (Priority: P1)

**Goal**: Provide ordered pre/post middleware pipeline with next-callback and short-circuit support.

**Independent Test**: Middleware chain order, response post-processing, short-circuit, and failure handling are deterministic.

### Tests for User Story 6

- [X] T075 [P] [US6] Add middleware contract tests in tests/contract/test_middleware_pipeline_contract.json
- [X] T076 [P] [US6] Add Python middleware chain tests in tests/integration/python/test_middleware_pipeline.py
- [X] T077 [P] [US6] Add .NET middleware chain tests in tests/integration/dotnet/MiddlewarePipelineTests.cs
- [X] T078 [P] [US6] Add Java middleware chain tests in tests/integration/java/MiddlewarePipelineTest.java
- [X] T079 [P] [US6] Add middleware short-circuit and failure tests in tests/integration/python/test_middleware_short_circuit.py, tests/integration/dotnet/MiddlewareShortCircuitTests.cs, and tests/integration/java/MiddlewareShortCircuitTest.java

### Implementation for User Story 6

- [X] T080 [US6] Implement Python middleware registration and ordering in packages/python/ygo74/agent_runtime/middleware/registry.py
- [X] T081 [P] [US6] Implement .NET middleware registration and ordering in packages/dotnet/Ygo74.AgentRuntime/Middleware/MiddlewareRegistry.cs
- [X] T082 [P] [US6] Implement Java middleware registration and ordering in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/middleware/MiddlewareRegistry.java
- [X] T083 [US6] Implement Python middleware pipeline executor with next-callback in packages/python/ygo74/agent_runtime/middleware/pipeline.py
- [X] T084 [P] [US6] Implement .NET middleware pipeline executor with next-callback in packages/dotnet/Ygo74.AgentRuntime/Middleware/MiddlewarePipeline.cs
- [X] T085 [P] [US6] Implement Java middleware pipeline executor with next-callback in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/middleware/MiddlewarePipeline.java
- [X] T086 [US6] Implement middleware error-to-envelope mapping in packages/python/ygo74/agent_runtime/middleware/middleware_errors.py, packages/dotnet/Ygo74.AgentRuntime/Middleware/MiddlewareErrors.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/middleware/MiddlewareErrors.java

**Checkpoint**: Middleware pipeline works with deterministic chain semantics.

---

## Phase 9: User Story 7 - Shared Authentication Context and Developer Authorization (Priority: P1)

**Goal**: Runtime handles JWT/API-key user context; developers enforce authorization in their handlers.

**Independent Test**: Valid auth produces user context, developer deny rules block business execution.

### Tests for User Story 7

- [X] T087 [P] [US7] Add JWT and API-key auth contract tests in tests/contract/test_auth_context_contract.json
- [X] T088 [P] [US7] Add Python auth context integration tests in tests/integration/python/test_auth_context.py
- [X] T089 [P] [US7] Add .NET auth context integration tests in tests/integration/dotnet/AuthContextTests.cs
- [X] T090 [P] [US7] Add Java auth context integration tests in tests/integration/java/AuthContextTest.java
- [X] T091 [P] [US7] Add developer-owned authorization denial tests in tests/integration/python/test_authorization_denial.py, tests/integration/dotnet/AuthorizationDenialTests.cs, and tests/integration/java/AuthorizationDenialTest.java

### Implementation for User Story 7

- [X] T092 [US7] Implement Python JWT authentication and user projection in packages/python/ygo74/agent_runtime/domains/auth/jwt_authenticator.py
- [X] T093 [P] [US7] Implement .NET JWT authentication and user projection in packages/dotnet/Ygo74.AgentRuntime/Domains/Auth/JwtAuthenticator.cs
- [X] T094 [P] [US7] Implement Java JWT authentication and user projection in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/auth/JwtAuthenticator.java
- [X] T095 [US7] Implement Python API-key user-resolution hook integration in packages/python/ygo74/agent_runtime/domains/auth/apikey_authenticator.py
- [X] T096 [P] [US7] Implement .NET API-key user-resolution hook integration in packages/dotnet/Ygo74.AgentRuntime/Domains/Auth/ApiKeyAuthenticator.cs
- [X] T097 [P] [US7] Implement Java API-key user-resolution hook integration in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/auth/ApiKeyAuthenticator.java
- [X] T098 [US7] Implement structured auth/authz error mapping in packages/python/ygo74/agent_runtime/domains/auth/auth_errors.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Auth/AuthErrors.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/auth/AuthErrors.java
- [X] T099 [US7] Document developer-owned authorization extension points in docs/examples/python-langchain-fastapi/authorization.md, docs/examples/dotnet-agentframework/authorization.md, and docs/examples/java-springai-springboot/authorization.md

**Checkpoint**: Shared authentication and developer-owned authorization are complete.

---

## Phase 10: Polish and Cross-Cutting Concerns

**Purpose**: Final hardening, examples validation, observability validation, and end-to-end quality gates.

- [X] T100 [P] Validate log level/sink reconfiguration and OpenTelemetry redirection in tests/integration/python/test_observability_reconfiguration.py, tests/integration/dotnet/ObservabilityReconfigurationTests.cs, and tests/integration/java/ObservabilityReconfigurationTest.java
- [X] T101 [P] Validate domain discoverability in public API docs at docs/examples/README.md
- [X] T102 [P] Validate runnable examples execute end-to-end in docs/examples/dotnet-agentframework/, docs/examples/python-langchain-fastapi/, and docs/examples/java-springai-springboot/
- [X] T103 Run full contract suite in tests/contract/
- [X] T104 Run full integration suite in tests/integration/
- [X] T105 Run full parity suite in tests/parity/
- [X] T106 Execute quickstart verification steps in specs/001-openai-endpoint-exposure/quickstart.md
- [X] T107 Final documentation update for feature behavior in specs/001-openai-endpoint-exposure/quickstart.md
- [X] T108 [P] Add cross-language namespace identity conformance tests in tests/parity/test_namespace_identity.py, tests/integration/dotnet/NamespaceIdentityTests.cs, and tests/integration/java/NamespaceIdentityTest.java
- [X] T109 [P] Add cross-language performance budget tests for dispatch and streaming first-event latency in tests/performance/python/test_performance_budget.py, tests/performance/dotnet/PerformanceBudgetTests.cs, and tests/performance/java/PerformanceBudgetTest.java
- [X] T110 [P] Add performance threshold baselines and regression policy in tests/performance/baselines/performance_thresholds.json
- [X] T111 Enforce performance regression gate execution in .github/workflows/ci.yml

---

## Phase 11: Foundational for Discovery (Blocking Prerequisites)

**Purpose**: Build the shared agent descriptor contract, model, registry, and error surface required by every discovery story.

**CRITICAL**: No discovery user story work starts before this phase is complete.

- [X] T113 Add agent descriptor contract schema in specs/001-openai-endpoint-exposure/contracts/agent-descriptor-v1.schema.json
- [X] T114 Add agent descriptor schema conformance contract tests in tests/contract/test_agent_descriptor_schema.py
- [X] T115 Implement Python agent descriptor, capability set, and skill models in packages/python/ygo74/agent_runtime/domains/discovery/agent_descriptor.py
- [ ] T116 [P] Implement .NET agent descriptor, capability set, and skill models in packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/AgentDescriptor.cs
- [ ] T117 [P] Implement Java agent descriptor, capability set, and skill models in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/AgentDescriptor.java
- [X] T118 Implement Python descriptor registry with uniqueness and deterministic ordering in packages/python/ygo74/agent_runtime/domains/discovery/descriptor_registry.py
- [ ] T119 [P] Implement .NET descriptor registry with uniqueness and deterministic ordering in packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DescriptorRegistry.cs
- [ ] T120 [P] Implement Java descriptor registry with uniqueness and deterministic ordering in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DescriptorRegistry.java
- [ ] T121 (Python done) Implement discovery error codes reusing the existing error envelope in packages/python/ygo74/agent_runtime/domains/discovery/discovery_errors.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DiscoveryErrors.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DiscoveryErrors.java
- [ ] T122 (Python done) Export discovery domain entry points in packages/python/ygo74/agent_runtime/\_\_init\_\_.py, packages/dotnet/Ygo74.AgentRuntime/PublicApi.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/PublicApi.java

**Checkpoint**: Descriptor contract and registry exist; discovery stories can start.

---

## Phase 12: User Story 8 - Agent Descriptor Single Source of Truth (Priority: P2)

**Goal**: Developers declare agent identity and capabilities once, validated at initialization, bound to a route key.

**Independent Test**: Declare descriptors, read them back from the registry, and confirm defaulting, uniqueness enforcement, route binding, and capability-contradiction rejection - all before any discovery endpoint exists.

### Tests for User Story 8

- [X] T123 [P] [US8] Add descriptor registration and validation contract tests in tests/contract/test_descriptor_registration_rules.json
- [X] T124 [P] [US8] Add Python descriptor registry tests in tests/integration/python/test_agent_descriptor_registry.py
- [ ] T125 [P] [US8] Add .NET descriptor registry tests in tests/integration/dotnet/AgentDescriptorRegistryTests.cs
- [ ] T126 [P] [US8] Add Java descriptor registry tests in tests/integration/java/AgentDescriptorRegistryTest.java
- [ ] T127 (Python done) [P] [US8] Add duplicate identifier, unresolved route key, and capability contradiction fail-fast tests in tests/integration/python/test_descriptor_validation.py, tests/integration/dotnet/DescriptorValidationTests.cs, and tests/integration/java/DescriptorValidationTest.java
- [ ] T128 (Python done) [P] [US8] Add derived minimal descriptor tests for handlers registered without a descriptor in tests/integration/python/test_descriptor_defaults.py, tests/integration/dotnet/DescriptorDefaultsTests.cs, and tests/integration/java/DescriptorDefaultsTest.java

### Implementation for User Story 8

- [X] T129 [US8] Implement Python descriptor defaulting and minimal derived descriptor in packages/python/ygo74/agent_runtime/domains/discovery/descriptor_defaults.py
- [ ] T130 [P] [US8] Implement .NET descriptor defaulting and minimal derived descriptor in packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DescriptorDefaults.cs
- [ ] T131 [P] [US8] Implement Java descriptor defaulting and minimal derived descriptor in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DescriptorDefaults.java
- [ ] T132 (Python done) [US8] Implement capability-versus-configuration consistency validator in packages/python/ygo74/agent_runtime/domains/discovery/capability_validator.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/CapabilityValidator.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/CapabilityValidator.java
- [ ] T133 (Python done) [US8] Implement descriptor-to-route-key binding validation against the existing route registry in packages/python/ygo74/agent_runtime/domains/discovery/descriptor_binding.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DescriptorBinding.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DescriptorBinding.java
- [ ] T134 (Python done) [US8] Extend framework-native configuration binding with descriptor declaration in packages/python/ygo74/agent_runtime/domains/configuration/models.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Configuration/EndpointOptions.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/configuration/EndpointProperties.java
- [ ] T135 (Python done) [US8] Document descriptor declaration in docs/examples/python-langchain-fastapi/agent-descriptor.md, docs/examples/dotnet-agentframework/agent-descriptor.md, and docs/examples/java-springai-springboot/agent-descriptor.md

**Checkpoint**: A validated single source of truth exists for every exposed agent.

---

## Phase 13: User Story 9 - Provider-Compatible Model Discovery Endpoints (Priority: P2)

**Goal**: Expose OpenAI and Anthropic model listing and single-model retrieval, projected from the descriptor, with dialect selection and pagination.

**Independent Test**: List models in both dialects, retrieve single entries, paginate the Anthropic listing, and submit each advertised identifier as an invocation model value.

### Tests for User Story 9

- [X] T136 [P] [US9] Add discovery surface contract tests in tests/contract/test_discovery_surface_contract.json
- [X] T137 [P] [US9] Add Python model discovery endpoint tests in tests/integration/python/test_model_discovery_endpoints.py
- [ ] T138 [P] [US9] Add .NET model discovery endpoint tests in tests/integration/dotnet/ModelDiscoveryEndpointsTests.cs
- [ ] T139 [P] [US9] Add Java model discovery endpoint tests in tests/integration/java/ModelDiscoveryEndpointsTest.java
- [ ] T140 (Python done) [P] [US9] Add dialect selection tests for header present, header absent, and configuration override in tests/integration/python/test_discovery_dialect_selection.py, tests/integration/dotnet/DiscoveryDialectSelectionTests.cs, and tests/integration/java/DiscoveryDialectSelectionTest.java
- [ ] T141 (Python done) [P] [US9] Add Anthropic pagination and continuation indicator tests in tests/integration/python/test_discovery_pagination.py, tests/integration/dotnet/DiscoveryPaginationTests.cs, and tests/integration/java/DiscoveryPaginationTest.java
- [ ] T142 (Python done) [P] [US9] Add discovery-to-invocation round-trip tests asserting every advertised identifier routes to its agent in tests/integration/python/test_discovery_round_trip.py, tests/integration/dotnet/DiscoveryRoundTripTests.cs, and tests/integration/java/DiscoveryRoundTripTest.java
- [ ] T143 (Python done) [P] [US9] Add discovery error tests for unknown identifier, unsupported provider version, and invalid pagination in tests/integration/python/test_discovery_errors.py, tests/integration/dotnet/DiscoveryErrorsTests.cs, and tests/integration/java/DiscoveryErrorsTest.java
- [ ] T185 (Python done) [P] [US9] Add identifier matching tests rejecting case-variant and whitespace-padded identifiers, and empty-catalogue tests asserting a successful empty listing per dialect, in tests/integration/python/test_discovery_identifier_matching.py, tests/integration/dotnet/DiscoveryIdentifierMatchingTests.cs, and tests/integration/java/DiscoveryIdentifierMatchingTest.java

### Implementation for User Story 9

- [X] T144 [US9] Implement Python OpenAI model projection in packages/python/ygo74/agent_runtime/domains/discovery/openai_model_projection.py
- [ ] T145 [P] [US9] Implement .NET OpenAI model projection in packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/OpenAiModelProjection.cs
- [ ] T146 [P] [US9] Implement Java OpenAI model projection in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/OpenAiModelProjection.java
- [X] T147 [US9] Implement Python Anthropic model projection with list envelope in packages/python/ygo74/agent_runtime/domains/discovery/anthropic_model_projection.py
- [ ] T148 [P] [US9] Implement .NET Anthropic model projection with list envelope in packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/AnthropicModelProjection.cs
- [ ] T149 [P] [US9] Implement Java Anthropic model projection with list envelope in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/AnthropicModelProjection.java
- [ ] T150 (Python done) [US9] Implement provider dialect selector with header detection and configuration override in packages/python/ygo74/agent_runtime/domains/discovery/dialect_selector.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DialectSelector.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DialectSelector.java
- [ ] T151 (Python done) [US9] Implement Anthropic-style pagination with page size limits in packages/python/ygo74/agent_runtime/domains/discovery/pagination.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DiscoveryPagination.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DiscoveryPagination.java
- [ ] T152 (Python done) [US9] Implement additive capability extension section shared by both provider projections in packages/python/ygo74/agent_runtime/domains/discovery/capability_extensions.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/CapabilityExtensions.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/CapabilityExtensions.java
- [ ] T153 (Python done) [US9] Register model listing and single-model routes in packages/python/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Endpoints/EndpointAdapters.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/endpoints/EndpointAdapters.java
- [ ] T154 (Python done) [US9] Implement discovery surface enable/disable toggles returning structured not-found in packages/python/ygo74/agent_runtime/domains/discovery/discovery_configuration.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DiscoveryConfiguration.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DiscoveryConfiguration.java
- [ ] T186 (Python done) [US9] Implement exact case-sensitive identifier matching, empty-catalogue success responses, and the externally reachable base URL setting in packages/python/ygo74/agent_runtime/domains/discovery/discovery_configuration.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DiscoveryConfiguration.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DiscoveryConfiguration.java

**Checkpoint**: Provider-compatible clients can discover and then invoke every exposed agent.

---

## Phase 14: User Story 10 - A2A Agent Card From the Same Descriptor (Priority: P3)

**Goal**: Serve an A2A agent card projected from the descriptor and prove cross-surface consistency.

**Independent Test**: Retrieve the agent card and assert field-by-field equivalence with the provider model entries for every shared attribute.

### Tests for User Story 10

- [ ] T155 [P] [US10] Add agent card contract tests in tests/contract/test_agent_card_contract.json
- [ ] T156 [P] [US10] Add Python agent card tests in tests/integration/python/test_agent_card.py
- [ ] T157 [P] [US10] Add .NET agent card tests in tests/integration/dotnet/AgentCardTests.cs
- [ ] T158 [P] [US10] Add Java agent card tests in tests/integration/java/AgentCardTest.java
- [ ] T159 [P] [US10] Add cross-surface consistency tests asserting shared attributes are identical across all three projections in tests/parity/test_discovery_surface_consistency.py
- [ ] T160 [P] [US10] Add disabled agent card surface tests confirming provider model endpoints are unaffected in tests/integration/python/test_agent_card_disabled.py, tests/integration/dotnet/AgentCardDisabledTests.cs, and tests/integration/java/AgentCardDisabledTest.java

### Implementation for User Story 10

- [ ] T161 [US10] Implement Python agent card projection in packages/python/ygo74/agent_runtime/domains/discovery/agent_card_projection.py
- [ ] T162 [P] [US10] Implement .NET agent card projection in packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/AgentCardProjection.cs
- [ ] T163 [P] [US10] Implement Java agent card projection in packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/AgentCardProjection.java
- [ ] T164 [US10] Implement security scheme advertisement without secret material in packages/python/ygo74/agent_runtime/domains/discovery/security_scheme_projection.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/SecuritySchemeProjection.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/SecuritySchemeProjection.java
- [ ] T165 [US10] Register the well-known agent card route in packages/python/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Endpoints/EndpointAdapters.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/endpoints/EndpointAdapters.java
- [ ] T166 [US10] Document the agent card surface in docs/examples/python-langchain-fastapi/agent-card.md, docs/examples/dotnet-agentframework/agent-card.md, and docs/examples/java-springai-springboot/agent-card.md

**Checkpoint**: All three discovery surfaces are served from one descriptor with proven consistency.

---

## Phase 15: User Story 11 - Discovery Access Control and Visibility (Priority: P3)

**Goal**: Reuse the authentication layer for discovery and let developers filter which agents each caller sees.

**Independent Test**: Call the listing anonymously and authenticated, apply a visibility rule, and confirm hidden and forbidden agents behave as specified.

### Tests for User Story 11

- [ ] T167 [P] [US11] Add discovery authentication tests for public and authenticated modes in tests/integration/python/test_discovery_auth.py, tests/integration/dotnet/DiscoveryAuthTests.cs, and tests/integration/java/DiscoveryAuthTest.java
- [ ] T168 [P] [US11] Add visibility rule filtering tests in tests/integration/python/test_discovery_visibility.py, tests/integration/dotnet/DiscoveryVisibilityTests.cs, and tests/integration/java/DiscoveryVisibilityTest.java (Python covered by tests/integration/python/test_agent_access_policy.py)
- [ ] T169 [P] [US11] Add hidden agent tests confirming absence from listings and continued invocability in tests/integration/python/test_discovery_hidden_agents.py, tests/integration/dotnet/DiscoveryHiddenAgentsTests.cs, and tests/integration/java/DiscoveryHiddenAgentsTest.java
- [ ] T170 [P] [US11] Add indistinguishability tests confirming forbidden and non-existent agents return identical responses in tests/integration/python/test_discovery_indistinguishability.py, tests/integration/dotnet/DiscoveryIndistinguishabilityTests.cs, and tests/integration/java/DiscoveryIndistinguishabilityTest.java (Python covered by tests/integration/python/test_agent_access_policy.py)
- [ ] T187 [P] [US11] Add fail-closed tests for a visibility rule that raises and for a visibility rule that exceeds its evaluation deadline in tests/integration/python/test_discovery_visibility_failure.py, tests/integration/dotnet/DiscoveryVisibilityFailureTests.cs, and tests/integration/java/DiscoveryVisibilityFailureTest.java (Python partial: raise-path covered in test_agent_access_policy.py; deadline-exceeded path not implemented)

### Implementation for User Story 11

- [ ] T171 [US11] Wire discovery endpoints to the existing request authenticator in packages/python/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Endpoints/EndpointAdapters.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/endpoints/EndpointAdapters.java (Python done)
- [ ] T172 [US11] Implement the developer-owned visibility rule extension point in packages/python/ygo74/agent_runtime/domains/discovery/visibility_rule.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/IDiscoveryVisibilityRule.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DiscoveryVisibilityRule.java (Python done as `AgentAccessPolicy` in domains/discovery/agent_access_policy.py, reused for both discovery filtering and invocation gating)
- [ ] T188 [US11] Implement fail-closed visibility rule evaluation with a configurable deadline and structured failure logging in packages/python/ygo74/agent_runtime/domains/discovery/visibility_rule.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DiscoveryVisibilityEvaluator.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DiscoveryVisibilityEvaluator.java (Python partial: exceptions are caught, logged with agent_id, and treated as denied in DiscoveryService._is_authorized and fastapi_endpoints._build_raw_payload; a configurable evaluation deadline/timeout is not yet implemented)
- [ ] T173 [US11] Enforce hidden visibility and visibility-rule filtering in the registry listing path in packages/python/ygo74/agent_runtime/domains/discovery/descriptor_registry.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DescriptorRegistry.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DescriptorRegistry.java (Python done in DiscoveryService.list_models/_authorized_only)
- [ ] T174 [US11] Normalize denied retrieval to the not-found response shape in packages/python/ygo74/agent_runtime/domains/discovery/discovery_errors.py, packages/dotnet/Ygo74.AgentRuntime/Domains/Discovery/DiscoveryErrors.cs, and packages/java/ygo74-agent-runtime/src/main/java/com/ygo74/agentruntime/domains/discovery/DiscoveryErrors.java (Python done in DiscoveryService.get_model/_find_visible)
- [ ] T175 [US11] Document discovery access control and the visibility rule in docs/examples/python-langchain-fastapi/authorization.md, docs/examples/dotnet-agentframework/authorization.md, and docs/examples/java-springai-springboot/authorization.md (Python done)

**Checkpoint**: Discovery no longer leaks the agent inventory and honors developer-owned visibility.

---

## Phase 16: Discovery Polish and Cross-Cutting Concerns

**Purpose**: Performance, parity, observability, examples, and quickstart validation for the discovery surfaces.

- [ ] T176 [P] Add discovery performance budget tests for listing p95 at 100 agents and O(1) lookup in tests/performance/python/test_discovery_budget.py, tests/performance/dotnet/DiscoveryBudgetTests.cs, and tests/performance/java/DiscoveryBudgetTest.java
- [ ] T177 [P] Add discovery performance thresholds to tests/performance/baselines/performance_thresholds.json
- [ ] T178 [P] Add cross-language discovery parity tests in tests/parity/test_discovery_parity.py
- [ ] T179 [P] Add deterministic listing order tests across repeated requests in tests/parity/test_discovery_ordering.py
- [ ] T180 [P] Validate discovery structured logging emits request identifier and outcome without leaking credentials in tests/integration/python/test_discovery_observability.py, tests/integration/dotnet/DiscoveryObservabilityTests.cs, and tests/integration/java/DiscoveryObservabilityTest.java
- [ ] T181 [P] Update runnable examples to declare a descriptor and expose all three discovery surfaces in docs/examples/python-langchain-fastapi/, docs/examples/dotnet-agentframework/, and docs/examples/java-springai-springboot/
- [ ] T182 Run full contract, integration, parity, and performance suites in tests/
- [ ] T183 Execute quickstart discovery scenarios 13-17 in specs/001-openai-endpoint-exposure/quickstart.md
- [ ] T184 Update the implementation snapshot for discovery in specs/001-openai-endpoint-exposure/quickstart.md

---

## Dependencies and Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies.
- Foundational (Phase 2): depends on Setup and blocks all user stories.
- User Stories (Phases 3-9): depend on Foundational.
- Polish (Phase 10): depends on completed target user stories.
- Discovery Foundational (Phase 11): depends on Phase 2 contracts and on US5 route registry; blocks all discovery stories.
- Discovery Stories (Phases 12-15): depend on Phase 11.
- Discovery Polish (Phase 16): depends on completed discovery stories.

### User Story Dependencies

- **US1** (Endpoints non-stream): starts after Foundational.
- **US2** (Streaming): depends on US1 endpoint adapters and mappers.
- **US3** (Native configuration): starts after Foundational; integrates with US1/US2.
- **US4** (Standard exchange handler): starts after Foundational; integrates with US1.
- **US5** (Routing/dispatch): starts after Foundational; depends on US4 handler contracts.
- **US6** (Middleware chain): starts after Foundational; depends on US5 dispatcher core.
- **US7** (Auth context + authz): starts after Foundational; integrates with US5/US6 pipeline.
- **US8** (Agent descriptor source of truth): starts after Phase 11; depends on US3 configuration binding and US5 route registry for validation.
- **US9** (Provider model discovery): depends on US8 descriptors and on US1 endpoint registration; the round-trip guarantee also depends on US5 routing.
- **US10** (A2A agent card): depends on US8 descriptors; consistency tests additionally depend on US9 projections.
- **US11** (Discovery access control): depends on US9 and US10 surfaces existing, and on US7 authentication.

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
- Discovery Foundational language tasks T116/T117, T119/T120 can run in parallel after their Python counterparts.
- US9 OpenAI and Anthropic projections are independent files and can be built in parallel per language.
- US10 agent card projection can be built in parallel with US9 provider projections once US8 is complete; only the cross-surface consistency test T159 needs both.
- Serialization point: T153, T165, and T171 all edit the same three endpoint adapter files. They MUST NOT run concurrently even when their stories otherwise proceed in parallel.
- Serialization point: T154 and T186 both edit the discovery configuration files, and T172 and T188 both edit the visibility rule files. Run each pair sequentially.

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

### US8

- Run in parallel:
  - T123, T124, T125, T126, T127, T128
  - T130, T131

### US9

- Run in parallel:
  - T136, T137, T138, T139, T140, T141, T142, T143, T185
  - T145, T146, T148, T149

### US10

- Run in parallel:
  - T155, T156, T157, T158, T160
  - T162, T163

### US11

- Run in parallel:
  - T167, T168, T169, T170, T187

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

### Discovery Increment (Phases 11-16)

1. Complete Phase 11 to establish the descriptor contract, model, and registry.
2. Deliver US8 as the discovery MVP: a validated single source of truth, testable with no endpoint exposed.
3. Add US9 to make agents visible and selectable by provider-compatible clients. This is the increment that delivers the requested `/v1/models` behavior end to end.
4. Add US10 to prove the shared source works for the richer A2A card and to lock cross-surface consistency.
5. Add US11 to close the information-disclosure surface.
6. Finish with Phase 16 performance, parity, observability, and quickstart validation.

### Multi-Developer Strategy

1. Team A: Python track tasks for active phase.
2. Team B: .NET track tasks for active phase.
3. Team C: Java track tasks for active phase.
4. Shared QA: contract/parity tests and cross-language examples.

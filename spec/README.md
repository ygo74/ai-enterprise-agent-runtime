# AI Enterprise Agent Runtime — System Specification

This directory describes the library as it exists in this repository: its
public responsibilities, runtime flow, contracts, language boundaries, and
security behavior. It is the durable system-level specification. It describes
the current system rather than a proposed change or the history of a feature.

The repository contains Python, .NET, and Java implementations. Their shared
core is provider-neutral request/response exchange, routing, authentication
building blocks, and middleware. Python also supplies a larger agent-oriented
surface: optional configuration-directory and `.env` loading, fixed YAML
manifest schemas and loaders, the framework-neutral reasoning contract, agent
discovery, application-security primitives, user-context construction, and
conversation and approval APIs. The session APIs include a generic
`AgentConversation` container, an `HttpConversationEngine`, and the
`ConversationRuntimeCache`; the approval APIs include a bounded, framework
neutral `ApprovalLoop` alongside confirmation and gated-operation primitives.
The optional MCP client provides generic binding loading and validation, lazy
stdio/streamable-HTTP connection lifecycle, a typed dialect registry, and one
asynchronous HTTPX pool per HTTP server in an agent registry. It uses typed
retry and circuit-breaker policies shared with the Python security package,
which separately manages synchronous HTTPX lookups for remote JWT/OIDC keys.
A separate Python package hosts MCP servers. These Python capabilities are not
implied to have .NET or Java equivalents; the parity document records their
current language boundary.

The generic conversation, approval-loop, and MCP client APIs address repeated
integration code in applications that combine HTTP conversations with agent
frameworks and MCP tools. They let an application reuse conversation state and
turn handling, bounded approval questions and turns with safe abandonment,
binding validation, connection lifecycle, and dialect dispatch. The application
still owns framework state, business and authorization policy, credentials,
and concrete dialects. The affected domain specifications below describe these
boundaries and behaviors.

The accepted `agent.yaml` and `skill.yaml` structures are versioned Python API
contracts. Their typed input models, packaged Draft 2020-12 schemas, identifiers,
and documentation evolve together; semantic permission and security-floor
checks remain runtime behavior.

## Documents

| Area | Specification |
|---|---|
| System purpose and request flow | [Architecture overview](architecture/system-overview.md) |
| Runtime domains and dependency boundaries | [Component model](architecture/component-model.md) |
| Request, response, error, and stream values | [Exchange contract](contracts/exchange-contract.md) |
| Authenticated identity and correlation during one invocation | [Agent invocation context](contracts/agent-invocation-context.md) |
| Typed agent results, content, usage, and streaming lifecycle | [Agent output and streaming](contracts/agent-output-and-streaming.md) |
| Provider-compatible invocation and streaming | [Endpoint surfaces](endpoints/provider-surfaces.md) |
| Trusted factories, identity-scoped state, and managed HTTP lifecycle | [Managed native-agent worker](endpoints/managed-agent-worker.md) |
| Agent descriptors and model listings | [Agent catalog](discovery/agent-catalog.md) |
| Delivered agent and skill manifests | [Agent manifests](configuration/agent-manifests.md) |
| Authentication, agent access, and authorization | [Authentication and authorization](security/authentication-and-authorization.md) |
| Permission, audit, operation, and untrusted-content primitives | [Application security](security/application-security-primitives.md) |
| Route selection, dispatch, and middleware composition | [Routing and middleware](runtime/routing-and-middleware.md) |
| Framework-neutral typed model reasoning | [Reasoning port](runtime/reasoning.md) |
| Routing, middleware, conversation containers, HTTP turn handling, and cache | [Pipelines and state](runtime/pipelines-and-state.md) |
| Confirmation, gated operations, and bounded approval-loop orchestration | [Human approval](runtime/human-approval.md) |
| Microsoft Agent Framework result, session, and worker binding | [Agent Framework integration](integrations/agent-framework.md) |
| LangChain result conversion, native LangGraph conversations, and managed worker | [LangChain and LangGraph integration](integrations/langchain-langgraph.md) |
| MCP bindings, client connections, dialect registry, and server responsibilities | [MCP integration](mcp/client-and-server.md) |
| Distributions, configuration, logging, and validation | [Packaging and operations](operations/packaging-configuration-observability.md) |
| Logging and incomplete telemetry hooks | [Observability](operations/observability.md) |
| Implemented behavior by language | [Language support and parity](compatibility/language-status.md) |

## Reading order

Start with the architecture overview and component model. The exchange,
invocation-context, and typed-output contracts define the values used across
endpoints. Endpoint, discovery, configuration, and security documents then
describe externally visible behavior. The runtime and framework integration
pages explain how applications compose workers, conversations, approval, and
reasoning. MCP and operations pages describe optional hosting and deployment
boundaries. The language support document records current parity limits.

## Sources of behavior

The implementation and integration tests define what the runtime does. The
main package entry points are under `packages/`; current guides are under
`doc/`; runnable samples are under `samples/`; behavior tests are under
`tests/`. This specification summarizes those
sources and calls out incomplete or language-specific areas rather than treating
design intent as implemented behavior.

Task-specific design records remain under
[`spec/implementation/`](implementation/README.md). Keep each issue's SPEC and
PLAN there while work is active; consolidate durable behavior into the relevant
domain pages in `spec/` without removing the issue tracking record. The active
Speckit feature directory under `specs/` remains separate from this consolidated
system specification.

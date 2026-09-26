# AI Enterprise Agent Runtime — System Specification

This directory describes the library as it exists in this repository: its
public responsibilities, runtime flow, contracts, language boundaries, and
security behavior. It is the durable system-level specification. It describes
the current system rather than a proposed change or the history of a feature.

The repository contains three language implementations. Their shared core is
provider-neutral request/response exchange, routing, authentication-related
types, and middleware building blocks. The Python implementation currently has
additional agent, discovery, security, approval, session, and MCP domains; those
capabilities are not yet at .NET/Java parity.

## Documents

| Area | Specification |
|---|---|
| System purpose and request flow | [Architecture overview](architecture/system-overview.md) |
| Runtime domains and dependency boundaries | [Component model](architecture/component-model.md) |
| Request, response, error, and stream values | [Exchange contract](contracts/exchange-contract.md) |
| Provider-compatible invocation and streaming | [Endpoint surfaces](endpoints/provider-surfaces.md) |
| Agent descriptors and model listings | [Agent catalog](discovery/agent-catalog.md) |
| Authentication, agent access, and authorization | [Authentication and authorization](security/authentication-and-authorization.md) |
| Permission, audit, operation, and untrusted-content primitives | [Application security](security/application-security-primitives.md) |
| Routing, middleware, and conversation state | [Pipelines and state](runtime/pipelines-and-state.md) |
| Confirmation and gated operations | [Human approval](runtime/human-approval.md) |
| MCP client and server responsibilities | [MCP integration](mcp/client-and-server.md) |
| Distributions, configuration, logging, and validation | [Packaging and operations](operations/packaging-configuration-observability.md) |
| Implemented behavior by language | [Language support and parity](compatibility/language-status.md) |

## Reading order

Start with the architecture overview and component model. The exchange contract
defines the common boundary used by endpoint adapters. Endpoint, discovery, and
security documents then describe externally visible behavior. The runtime and
MCP documents cover optional composition building blocks, and the language
support document records current parity limits.

## Sources of behavior

The implementation and integration tests define what the runtime does. The
main package entry points are under `packages/`; current usage guides are under
`docs/`; behavior tests are under `tests/`. This specification summarizes those
sources and calls out incomplete or language-specific areas rather than treating
design intent as implemented behavior.

Task-specific design records remain under `docs/tasks/`. The older Speckit
feature directory under `specs/` is separate from this consolidated system
specification.

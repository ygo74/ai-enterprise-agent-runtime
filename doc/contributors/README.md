# Contributor documentation

This guide explains how the runtime is organized and where to change each
domain. It complements the [system specification](../../spec/README.md), which
describes supported behavior and public contracts.

## Domains

- [Architecture and package boundaries](architecture.md)
- [Contracts and mapping](contracts.md)
- [Endpoints and streaming](endpoints.md)
- [Routing and middleware](routing-middleware.md)
- [Authentication and application security](security.md)
- [Delivered configuration](configuration.md)
- [Agent discovery](discovery.md)
- [Conversations and cache lifecycle](conversations.md)
- [Managed native-agent worker](managed-worker.md)
- [Human approval](approval.md)
- [Framework-neutral reasoning](reasoning.md)
- [MCP client and server hosting](mcp.md)
- [Microsoft Agent Framework integration](agentframework.md)
- [LangChain and LangGraph integration](langchain.md)
- [Observability](observability.md)
- [Language parity and validation](parity-validation.md)
- [Detailed parity status](parity-status.md)

## Suggested reading path

Start with package boundaries, then read the domain page you plan to change.
Follow the linked implementation and tests before changing a contract. Shared
wire formats and schemas are under `specs/`; current system behavior is under
`spec/`; runnable consumer examples are indexed under `samples/` by language.

Detailed Python package and integration guides are indexed in
[`../python/README.md`](../python/README.md).

## Repository instructions

Read [`AGENTS.md`](../../AGENTS.md) before implementation work. It points to
the project constitution, active feature plans, engineering rules, and
language-specific instructions. Python changes must also follow
[`python.instructions.md`](../../.github/instructions/python.instructions.md).

# User and operator guides

Follow these guides in order, from installing the runtime to operating an
agent. They describe shared runtime concepts and use language-neutral HTTP/JSON
examples. For implementation code and language-specific setup, use the relevant
language guide; Python details are in the [Python library guides](../python/README.md).

## Guides

1. [Install the runtime](getting-started.md)
2. [Bring your own agent](bring-your-own-agent.md): provide business rules,
   tools, skills, and the system prompt; choose an integration approach.
3. [Host an agent](agent-hosting.md): choose application-owned or runtime-owned
   hosting and understand the hosting options.
4. [Endpoints and outputs](endpoints-and-outputs.md): call supported provider
   surfaces and understand response formats.
5. [Framework integrations](framework-integrations.md): connect an existing
   agent framework to the runtime.
6. [Conversations](conversations.md): keep related turns associated and choose
   state ownership.
7. [Agent, skill, and MCP configuration](mcp.md): describe agents, tools, and
   remote MCP services.
8. [Human approval](human-approval.md): pause a side-effecting operation for a
   decision.
9. [Host an MCP server](mcp-server-hosting.md): expose tools over HTTP safely.
10. [Security](security.md): authenticate callers and enforce authorization.
11. [Agent discovery](discovery.md): publish and filter agent descriptors.

## Runnable samples

Browse the [language-first sample catalog](../../samples/README.md). The Python
catalog currently contains a [basic runtime quickstart](../../samples/python/python-fastapi-quickstart/README.md),
[LangChain examples](../../samples/python/python-langchain-fastapi/README.md),
[Microsoft Agent Framework examples](../../samples/python/python-agentframework-fastapi/README.md),
and an [MCP server](../../samples/python/python-mcp-server/README.md).

For contributor architecture, see [contributor guides](../contributors/README.md).
For feature behavior and rationale, see the [system specification](../../spec/README.md).

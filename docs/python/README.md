# Python library documentation

The Python runtime is split into six installable distributions. Start with the
[installation guide](installation.md) to choose one, then use the [quickstart](quickstart.md)
to serve a local endpoint.

## Guides

- [Native agents and managed workers (Python pilot)](native-agents.md): native
  factories, declarative definitions, shared streaming/approvals and local hosting
- [Installation and package selection](installation.md)
- [Quickstart: serve an agent with FastAPI](quickstart.md)
- [Agent runtime](agent-runtime.md): endpoint setup, handler payloads, routing,
  middleware, sessions, approvals, manifest loading, and observability
- [Typed outputs and migration](typed-outputs.md): neutral results/events,
  media, notifications and protocol filtering
- [LangChain integration](langchain.md): independently installed output adapters
- [Microsoft Agent Framework integration](agentframework.md): independently
  installed result and update adapters
- [Agent description and OpenAI model discovery](agent-discovery.md):
  descriptors, registration options, and the `v1/models` endpoints
- [Human-in-the-loop approval](human-in-the-loop.md): confirmation policy,
  execution gates, and approvals across HTTP requests
- [Security](security.md): FastAPI and MCP authentication, caller context,
  agent and handler authorization, safe header forwarding, and application
  permission, audit, operation-classification, and untrusted-content primitives
- [MCP](mcp.md): MCP client bindings and MCP server hosting

## Runnable examples

- [Minimal FastAPI quickstart](../examples/python-fastapi-quickstart/README.md):
  local echo agent without external credentials
- [LangChain + FastAPI examples](../examples/python-langchain-fastapi/README.md):
  richer agent integration, authentication, descriptors, and human approval
- [Python MCP server](../examples/python-mcp-server/README.md): protected
  streamable HTTP server
- [Microsoft Agent Framework + FastAPI](../examples/python-agentframework-fastapi/README.md):
  SDK contents converted to the neutral output contract

## References

- [Consolidated system specification](../../spec/README.md)
- [OpenAI and Anthropic endpoint surfaces](../../spec/endpoints/provider-surfaces.md)
- [Standard exchange contract](../../spec/contracts/exchange-contract.md)
- [OpenAI and Anthropic machine-readable endpoint contract](../../specs/001-openai-endpoint-exposure/contracts/endpoint-surface-contract.md)
- [Standard exchange schema](../../specs/001-openai-endpoint-exposure/contracts/standard-exchange-v1.schema.json)
- [Typed output contract](../../specs/001-openai-endpoint-exposure/contracts/typed-output-contract.md)
- [Typed output v2 schema](../../specs/001-openai-endpoint-exposure/contracts/agent-output-v2.schema.json)
- [Agent descriptor schema](../../specs/001-openai-endpoint-exposure/contracts/agent-descriptor-v1.schema.json)
- [Feature quickstart and validation scenarios](../../specs/001-openai-endpoint-exposure/quickstart.md)

These guides and the [system specification](../../spec/README.md) describe the
currently implemented Python behavior. Public APIs and configuration can evolve;
use the linked machine-readable schemas and examples for the details relevant to
a specific integration.

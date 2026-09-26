# Python library documentation

The Python runtime is split into four installable distributions. Start with the
[installation guide](installation.md) to choose one, then use the [quickstart](quickstart.md)
to serve a local endpoint.

## Guides

- [Installation and package selection](installation.md)
- [Quickstart: serve an agent with FastAPI](quickstart.md)
- [Agent runtime](agent-runtime.md): endpoint setup, handler payloads, routing,
  middleware, sessions, approvals, and observability
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

## References

- [OpenAI and Anthropic endpoint contract](../../specs/001-openai-endpoint-exposure/contracts/endpoint-surface-contract.md)
- [Standard exchange schema](../../specs/001-openai-endpoint-exposure/contracts/standard-exchange-v1.schema.json)
- [Agent descriptor schema](../../specs/001-openai-endpoint-exposure/contracts/agent-descriptor-v1.schema.json)
- [Feature quickstart and validation scenarios](../../specs/001-openai-endpoint-exposure/quickstart.md)

These guides describe the currently implemented Python behavior. Public APIs and
configuration can evolve; follow the linked feature contracts and examples for
the details relevant to a specific integration.

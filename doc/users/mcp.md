# Agent, skill, and MCP configuration

Configuration declares which agent is available, what instructions it follows,
and which capabilities it may use. Keep these declarations separate from
operator secrets and from authorization decisions that need to be enforced at
runtime.

## Agent and skill configuration

An agent descriptor gives clients public metadata such as an ID, description,
version, and capabilities. A skill groups task guidance and tools that the
application chooses to make available. A system prompt supplies behavioral
instructions; it must not be the only control protecting a resource or
side-effecting operation.

## MCP client configuration

Model Context Protocol (MCP) lets an agent application connect to a service that
exposes tools. A binding maps a local tool name to a server endpoint, transport,
authentication settings, and remote tool name. Allow only the tools the agent
needs, keep credentials in an environment or secret manager, and enforce access
at the server as well as in the client application.

Configuration should be validated before use. Missing servers, duplicate names,
invalid transports, or unsupported authentication settings should fail clearly
rather than silently exposing a different tool.

For Python configuration fields, loader APIs, OAuth support, and lifecycle
rules, see the [Python MCP guide](../python/mcp.md). Runnable configurations are
available in the [LangChain](../../samples/python/python-langchain-fastapi/06-mcp-configuration/README.md)
and [MAF](../../samples/python/python-agentframework-fastapi/06-mcp-configuration/README.md)
examples.

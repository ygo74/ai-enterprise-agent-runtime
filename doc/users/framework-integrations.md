# Framework integrations

Framework integrations connect an agent built with an existing framework to
the runtime's endpoint and output contracts. An adapter translates framework
results and streaming updates; the application remains responsible for agent
instructions, business rules, tool permissions, and framework-specific state.

## Choose a supported integration

Support depends on the implementation language and the framework version. The
current Python integrations include LangChain/LangGraph and Microsoft Agent
Framework. Their runnable scenarios are listed in the [Python sample catalog](../../samples/python/README.md).

- [LangChain guide](../python/langchain.md): result and event adapters, worker
  options, and supported input profiles.
- [Microsoft Agent Framework guide](../python/agentframework.md): native MAF
  agents, result and update conversion, and current support limits.

## Shared request shape

A client sends the request to the endpoint registered by the host. For example:

```http
POST /v1/responses
Content-Type: application/json

{"model":"support-agent","input":"Summarize the service limits."}
```

The host selects the agent, invokes the framework adapter, and maps its output
to the selected provider response. The adapter does not make one framework's
features identical to another's. Review the integration guide and sample README
for limits such as input profiles, tool admission, streaming, and conversation
state.

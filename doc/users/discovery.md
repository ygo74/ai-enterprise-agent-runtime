# Agent discovery

Discovery lets a client list the agents an application has registered and read
their public descriptions. In the current Python OpenAI-compatible integration,
`GET /v1/models` lists descriptors and `GET /v1/models/{id}` returns one
registered descriptor.

A descriptor can publish an agent ID, description, version, owner, and
capabilities. Keep secrets and internal policy details out of public metadata.
If discovery is protected, apply the same access policy used for invocation so
clients cannot learn about agents they are not allowed to use.

For descriptor fields, registration, and access policy in Python, see [Agent
discovery](../python/agent-discovery.md). The [LangChain getting-started
sample](../../samples/python/python-langchain-fastapi/01-get-started/README.md)
shows a registered agent.

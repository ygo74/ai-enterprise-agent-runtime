# Install the runtime

The runtime is distributed as packages that can be added to an application.
Choose the package for the capabilities the application uses: endpoint hosting,
an agent-framework adapter, MCP client support, or MCP server hosting. Optional
integrations keep applications from taking dependencies on frameworks they do
not use.

Package names and installation instructions depend on the implementation
language. See the [Python package selection guide](../python/installation.md)
for Python. Future language guides can be linked from the
[sample and language index](../../samples/README.md).

## Make a first request

The [basic Python endpoint sample](../../samples/python/python-fastapi-quickstart/01-basic-endpoint/README.md)
shows a local echo service that needs no model-provider credential. With the
service running, send a provider-shaped request:

```http
POST /v1/responses
Content-Type: application/json

{"model":"echo-agent","input":"hello"}
```

The response contains `Echo: hello`. The [endpoints and outputs guide](endpoints-and-outputs.md)
explains the available request surfaces and response projections.

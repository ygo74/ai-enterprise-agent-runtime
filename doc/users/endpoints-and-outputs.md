# Endpoints and outputs

An endpoint accepts a provider-shaped request, maps it to a shared handler
payload, and converts the result to the provider's response format. Your
application supplies the agent logic. The current Python HTTP integration
supports these surfaces; other integrations may expose a different subset.

| Endpoint | Route |
|---|---|
| OpenAI Responses | `POST /v1/responses` |
| OpenAI Chat Completions | `POST /v1/chat/completions` |
| Anthropic Messages | `POST /v1/messages` |

## Make a request

Start the local echo service by following [Getting started](getting-started.md),
then send a JSON request:

```http
POST /v1/chat/completions
Content-Type: application/json

{"model":"echo-agent","messages":[{"role":"user","content":"hello"}]}
```

The response uses the Chat Completions shape and contains `Echo: hello`. If the
request fails, check that the application enabled this endpoint and registered
the requested agent or route.

## Output formats

Handlers return structured content and, when streaming, typed events. The
runtime maps supported text, tool, media, reasoning, notification, and usage
content to the selected endpoint. Provider surfaces may represent or filter
content differently. See the [structured output sample](../../samples/python/python-fastapi-quickstart/02-structured-outputs/README.md).

For Python output types, migration details, and supported content, see
[Typed outputs](../python/typed-outputs.md).

## Streaming

Streaming uses Server-Sent Events where supported. Set `stream` to `true`; the
handler must produce events rather than a completed response. Each provider has
its own event format. The [Python agent runtime guide](../python/agent-runtime.md)
describes event mapping and implementation limits.

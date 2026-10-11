# Endpoints, conversations, and outputs

An endpoint accepts a provider-shaped request, maps it to a common handler
payload, and converts the handler result back to the provider's response format.
Your application supplies the agent logic.

## Available HTTP endpoints

The FastAPI integration can register these routes:

| Endpoint | Route |
|---|---|
| OpenAI Responses | `POST /v1/responses` |
| OpenAI Chat Completions | `POST /v1/chat/completions` |
| Anthropic Messages | `POST /v1/messages` |

Select the routes your application needs when configuring the runtime. A
conversation identifier is application metadata; the endpoint adapter does not
choose durable storage for your agent state.

## Call an endpoint

Start the local echo service by following
[Getting started](getting-started.md). Then request a chat completion:

```bash
curl -sS http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"echo-agent","messages":[{"role":"user","content":"hello"}]}'
```

The response has the Chat Completions shape and contains `Echo: hello`. If you
receive a route error, check that the application enabled Chat Completions and
that the requested model or route key is registered.

## Typed outputs

Agent handlers return `AgentOutput` or typed output events. The runtime maps
supported text, tool, media, reasoning, notification, and usage content to the
selected endpoint. It does not accept a raw string or arbitrary result
dictionary as the public output contract in version 1.0.

For a structured response example, see
[`responses_structured_app.py`](../../samples/examples/python-fastapi-quickstart/responses_structured_app.py).
For content types and migration details, see
[Typed outputs](../../doc/python/typed-outputs.md).

## Streaming

Streaming uses Server-Sent Events. The request must set `stream` to `true`, and
the handler must return an async iterator of typed events. Each provider uses
its own event format. Do not return a normal `AgentOutput` for a streaming
request. See [Agent runtime](../../doc/python/agent-runtime.md) for the event
mapping and protocol-specific limits.

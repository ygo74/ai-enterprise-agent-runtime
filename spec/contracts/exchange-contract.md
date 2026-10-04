# Standard exchange contract

The exchange model is the runtime's provider-neutral representation of an
invocation. Its purpose is to keep handler logic independent of which supported
provider dialect carried the request.

## Request

`StandardExchangeRequest` contains:

| Field | Meaning |
|---|---|
| `request_id` / `requestId` | Request correlation identifier. |
| `route_key` / `routeKey` | Internal handler-selection key. It is distinct from a public agent/model ID. |
| `endpoint_type` / `endpointType` | One of the three canonical endpoint identifiers. |
| `input` | Normalized user input. Its contents remain application/provider data rather than a runtime-specific typed prompt model. |
| `stream` | Whether the caller requested streamed output; defaults to false. |
| `metadata` | Additional non-secret request metadata, including only explicitly forwarded headers. |
| `auth_context` / `authContext` | Normalized authenticated caller context, or absent/null for allowed anonymous requests. |
| `provider_options` / `providerOptions` | Optional raw JSON key/value collection for provider request options not represented by normalized fields. Absent when the adapter has no provider options to preserve. |

The adapter may also retain the requested model ID and provider-specific stream
options in metadata or its boundary payload. A route key must be resolved before
dispatch. Explicit route-key metadata takes precedence over model resolution in
the Python HTTP adapter; a known public model ID resolves to its descriptor's
internal route key, and otherwise the configured default route is used.

## Response

`StandardExchangeResponse` contains a request ID, status, optional output,
optional `ErrorEnvelope`, and metadata. The supported status values are
`success` and `error`:

- A successful response carries `output`.
- An error response carries `error`.
- `ResponseValidator` rejects a status outside those values and rejects a
  missing output or error for the corresponding status.

For Python agents 1.0, successful output is a typed `AgentOutput`, either returned
directly or carried by the typed exchange envelope. Its content is independent
of the invoking protocol. Raw dictionaries/strings and native Responses output
items are not alternate output contracts. .NET/Java retain historical v1.
See the [typed output contract](../../specs/001-openai-endpoint-exposure/contracts/typed-output-contract.md)
and [migration guide](../../docs/python/typed-outputs.md).

## Errors

`ErrorEnvelope` contains `code`, `category`, `message`, optional `details`,
optional `request_id`, and optional `retryable`. The cross-language category
vocabulary is:

- `validation`
- `authentication`
- `authorization`
- `routing`
- `mapping`
- `handler_execution`
- `configuration`

The Python FastAPI adapter maps validation to HTTP 400, authentication to 401,
authorization to 403, routing to 404, and other handler errors to 500. Provider
response details are defined by the adapter; the internal error envelope
remains the shared diagnostic value.

## Streaming events

Python handlers produce typed `AgentStreamEvent` values. Content/event identities
are neutral; response IDs, indices and SSE sequences are projection state.
Valid unsupported content is filtered with explicit safe diagnostics. Notifications
are visible in streaming and excluded from the non-streaming business result.
Invalid events and execution failures are errors, not filtering decisions.

The historical v1 `chunk`/`completion`/`error` contract remains the implemented
contract in .NET/Java until the separately tracked parity work is delivered.

## Serialization and language shape

Python uses snake-case dataclass fields. .NET uses Pascal-case record members,
and Java uses camel-case record members. The shared serialized contract uses
camel-case names such as `requestId`, `endpointType`, and `authContext`.
Provider wire formats are mapped separately and do not adopt this casing.

The Python FastAPI integration currently calls a user entrypoint with a
normalized dictionary containing the fields above. The typed Python model is
available to application code, but the adapter does not require the user
entrypoint to accept that dataclass. .NET and Java dispatch interfaces use
their typed `StandardExchangeRequest` records.

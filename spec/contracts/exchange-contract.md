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

The runtime does not prescribe the application's result object. Provider
adapters render plain text or structured output according to their supported
mapping behavior.

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

`StandardStreamingExchangeEvent` carries a request ID, monotonically assigned
sequence, event type, optional delta, optional final output, and optional
error. The event types used by the contract are `chunk`, `completion`, and
`error`. Provider adapters translate these events into their provider-specific
server-sent event envelopes.

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

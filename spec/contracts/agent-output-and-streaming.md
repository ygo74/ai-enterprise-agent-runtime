# Agent output and streaming contract

## Purpose

Provider APIs return different content types, usage fields, and stream events.
Without one output model, an agent implementation must know which API will
carry its result. The Python runtime uses `AgentOutput` and
`AgentStreamEvent` as a neutral boundary between agent execution and provider
projection.

This v2 contract is implemented by the Python packages. .NET and Java still use
their earlier output and stream shapes; the shared endpoint names do not imply
that they implement this v2 contract.

## Complete results

`AgentOutput` contains ordered content, optional token usage, and a termination
status. Content may be text with URL citations, stream-only notification text,
reasoning with an explicit exposure flag, tool calls and results, or image and
audio media. A tool call identifies whether the agent runs it internally or
hands it to the client. Media references preserve their URI or encoded data and
declared type; the runtime does not fetch or transcode media.

Termination is `success`, `incomplete`, or `failed`. Failure details use the
standard `ErrorEnvelope`. Incomplete output is distinct from both a successful
answer and a failed invocation. Token input/output counts are required when a
usage value is supplied; total, cached, reasoning, and cache-write counts remain
unknown when the provider did not report them. The runtime never fills unknown
usage with zero or infers one counter from another.

## Incremental results

`AgentStreamEvent` represents either one complete item or a content lifecycle:
start, zero or more typed deltas, and end. Events also carry cumulative usage
snapshots and exactly one terminal status. Content identities correlate events
inside the neutral stream; protocol-specific indices and sequence IDs are added
by the projector.

Notifications are visible in a stream but are not part of the non-streaming
business answer. Usage events are snapshots of the latest cumulative counts,
not increments. Audio fragments carry sequence numbers; tool argument fragments
remain serialized text until the call is complete.

## Provider projection and unsupported content

Provider adapters validate lifecycle and map the neutral content they support.
Valid content that a selected protocol cannot represent is filtered with safe
diagnostics. Invalid event order, malformed tool calls, and execution failures
remain errors. Reasoning is hidden unless the application explicitly marks it
exposable and the protocol supports that projection. Internal tool activity is
not automatically made into a client-executable tool request.

For OpenAI Responses streaming, a failed invocation emits one standalone
`error` event followed by one `response.failed` lifecycle event. The two events
carry the same stable public error; the standalone event includes the nested
error envelope expected by the OpenAI Python SDK. A failed stream never emits
`response.completed`. If execution fails before streaming headers are sent,
the HTTP request instead receives a structured 500 response. Once headers are
sent, the already-committed HTTP status cannot change, so clients must inspect
the stream's terminal error rather than treating HTTP 200 as success.

Python FastAPI failure logs include correlation fields, exception type, and
raising origin, but do not log arbitrary exception messages. Only explicitly
marked, credential-free diagnostic metadata is included; it is flattened and
bounded. For missing MCP environment references this metadata may identify the
configuration file, field, and variable name, never the referenced value. See
the [observability specification](../operations/observability.md).

The three protocol projections have different requirements. Anthropic Messages
requires genuine input and output usage in its response and before visible
stream content. The runtime does not invent a zero-usage baseline after model
execution or buffer content to hide missing usage. OpenAI surfaces can represent
some responses without usage. Exact content support is maintained in the
[Python typed output guide](../../doc/python/typed-outputs.md).

## Acceptance and limits

- Agent handlers return typed `AgentOutput` or typed stream events; native
  provider payloads, strings, and unvalidated dictionaries are not alternate
  output contracts.
- Complete results preserve content order, known usage, and explicit
  termination.
- Stream items have valid identities and lifecycle; one invocation ends with
  one terminal event.
- Unsupported protocol projection is visible through diagnostics and does not
  silently stringify or invent content.
- Unknown token counts remain unknown.
- This contract's v2 implementation is Python-only today.

The public types are [`agent_output.py`](../../packages/python/agents/ygo74/agent_runtime/domains/contracts/agent_output.py)
and [`stream_events.py`](../../packages/python/agents/ygo74/agent_runtime/domains/contracts/stream_events.py).
The integration suites include
[`test_neutral_stream_lifecycle.py`](../../tests/integration/python/test_neutral_stream_lifecycle.py),
[`test_streaming_endpoints.py`](../../tests/integration/python/test_streaming_endpoints.py),
and framework adapter tests. The older machine-readable feature contract remains
available in [`typed-output-contract.md`](../../specs/001-openai-endpoint-exposure/contracts/typed-output-contract.md).

# Typed agent outputs and migration

Python agents 1.0 introduces a provider-neutral output contract. The incoming
handler mapping remains unchanged. Your handler returns an `AgentOutput` or an
asynchronous iterator of typed `AgentStreamEvent` values. The runtime projects
those values into the protocol the caller selected.

The definitive fields and support matrix are in the
[typed output contract](../../specs/001-openai-endpoint-exposure/contracts/typed-output-contract.md).
The [local echo example](../examples/python-fastapi-quickstart/app.py) and
[structured example](../examples/python-fastapi-quickstart/responses_structured_app.py)
demonstrate runnable handlers.

## Construct the pivot directly

```python
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput, Notification, TextContent,
)

output = AgentOutput((
    Notification("Checking the local knowledge base."),
    TextContent("The answer is 42."),
))
```

Return `output` from your handler. With `stream=false`, the notification is
filtered and logged. With `stream=true`, it is projected as visible progress
text. Returning a completed result does not make agent execution incremental:
use typed events to release content while your agent is still running.

```python
from collections.abc import AsyncIterator
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent, ContentEnd, ContentEvent, ContentStart, TerminalEvent, TextDelta,
)

async def answer_stream() -> AsyncIterator[AgentStreamEvent]:
    yield ContentEvent("progress", Notification("Checking references."))
    yield ContentStart("answer", TextContent(""))
    yield TextDelta("answer", "The answer ")
    yield TextDelta("answer", "is 42.")
    yield ContentEnd("answer")
    yield TerminalEvent()
```

Use one content identity across its start, deltas and end. Emit the terminal
only after successful completion; do not announce success from a `finally`
block. An exception or cancellation must propagate.

## Responsibilities

- Your application selects which native framework updates to expose.
- An independently installed [LangChain](langchain.md) or
  [Agent Framework](agentframework.md) adapter converts native values to the
  neutral contract. You can also construct the types yourself.
- Core projection classes create wire envelopes, message/content indices,
  response identifiers, SSE sequences and terminal events.
- You do not need to know whether the caller used Responses, Chat Completions
  or Anthropic Messages.

One SDK update may contain several contents, so conversion may yield multiple
pivot events. A state snapshot is not necessarily a delta. Adapters provide an
inspectable unsupported outcome instead of stringifying arbitrary objects.
You may ignore a native event or convert it deliberately into a notification.

For neutral JSON snapshots, use `AgentOutputSerializer().serialize(value)` from
`ygo74.agent_runtime.domains.contracts`. Its explicit `type`/`value` wrappers
preserve distinctions such as notification versus answer and atomic content
versus content start. A plain dataclass dictionary loses those identities.
These snapshots follow the versioned output schema; they are neither provider
payloads nor accepted raw handler outputs.

## Notifications and filtering

Use the notification type for progress such as "Calling search tool".
Notifications are visible as text in streaming, but are excluded from the
non-streaming business result with a filtering diagnostic. Do not mark them as
answer text if you expect that exclusion.

A valid pivot value unsupported by the selected protocol is filtered by the
runtime with a correlated diagnostic. Its linked lifecycle/deltas are filtered
together so clients never receive orphaned blocks. Logs identify the content
type, protocol and reason, not tool arguments/results, encoded data or sensitive
URLs. A wholly filtered output is empty, not an invented textual answer.

Invalid data, malformed event order and handler execution failures are errors,
not protocol limitations. The producer is closed on termination, cancellation
or failure. The runtime does not emit a successful terminal after an error.

## Usage counters

Supply only observed model-token counts through `TokenUsage` and cumulative
`UsageEvent` snapshots. Missing totals or cache/reasoning details stay unknown;
the runtime does not estimate them from text or substitute zero.

Chat Completions usage requires a known total. Responses usage additionally
requires known cache-read, cache-write and reasoning counts, represented by
`cached_input_tokens`, `cache_write_input_tokens` and
`reasoning_output_tokens`. Incomplete OpenAI usage is omitted with a diagnostic,
while answer content remains available.

Anthropic requires input/output usage in its message envelope. A completed
result without those counts fails explicitly. An asynchronous producer must
emit a genuine initial `UsageEvent` before visible content; later cumulative
snapshots update both input and output counts. The runtime neither silently
buffers the entire stream nor invents a starting counter. A completed
`AgentOutput` with known usage can seed its streaming envelope directly.

The offline Echo example explicitly reports zero because it invokes no model.
That is producer-owned knowledge, not a fallback for unknown real-agent usage.
After backend execution, unknown final consumption must be reported as a
failure or limitation, never represented by reusing a pre-execution baseline.

## Tools, reasoning and media

Internal tool activity is distinct from an instruction for the client to execute
a function. The runtime does not execute tools for your agent. Select internal
activity deliberately or render it as a notification when appropriate.

Only explicitly exposable reasoning should be sent. Framework-internal messages,
sub-agent state and protected reasoning are not automatically the final answer.

Image and audio types preserve URI or encoded data, MIME/format and correlation.
Audio fragments and transcriptions retain their identity and order. The runtime
does not fetch URLs, transcode codecs or manufacture hosted-provider tool calls.
Protocol support varies by content and mode; consult the support matrix rather
than assuming that every media value is representable by every endpoint.

In the initial projections, assistant images and streaming audio are filtered
on all three surfaces. URI audio is also filtered. Non-streaming Chat
Completions audio requires encoded data and a genuine `expires_at`; neither
the core nor an adapter invents an expiry. The pivot still validates and
preserves those media types for explicit selection and future projections.
Exposable reasoning is currently projected only as a Responses summary;
internal tool observations/results are filtered rather than turned into
client-execution requests.

Text may carry typed URL citations with genuine URL, title and character
offsets. Responses preserves them; other projections retain the text and log
the unsupported citation metadata. Adapters must not guess missing offsets.

## Breaking migration

There is no compatibility path for:

- raw string/dictionary handler outputs or text/dictionary stream chunks;
- `OpenAIResponsesResult` as a developer output model;
- `OpenAIResponsesStreamEvent` or complete Responses payload passthrough;
- the generic historical `chunk`/`completion`/`error` Python streaming contract.

Construct typed contents/results/events or use one of the integration adapters.
Keep raw SDK values inside your application until that conversion boundary.
Migrate notifications separately from answer text, terminate event streams
explicitly, and do not create provider lifecycle frames yourself.

The agents and meta-package major release records this output break. Security
and MCP hosting APIs are not redesigned. Framework distributions are installed
explicitly and do not become core or base meta-package dependencies.

The output contract is versioned independently from historical Standard
Exchange v1. Its .NET/Java implementation is a separate follow-up; existing v1
tests in those runtimes are not evidence of new-contract parity.

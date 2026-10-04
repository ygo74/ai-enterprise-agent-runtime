# Microsoft Agent Framework output integration

Install explicitly; the agents library and meta base do not depend on an agent SDK:

```powershell
python -m pip install "ygo74-agent-runtime-agentframework==1.0.0" "ygo74-agent-runtime-agents[http]>=1.0.0,<2"
```

Requires Python 3.12+, runtime agents 1.x, and
`agent-framework-core>=1.18.0,<1.19`. The adapter uses the verified 1.18 unified
`Content` API, not older `ChatMessage`/`TextContent` SDK classes. The lightweight
core distribution supplies `agent_framework`; provider integrations may be
installed separately by your application.

The package owns only `ygo74.agent_runtime.integrations.agentframework` and its
`py.typed` marker. It neither imports FastAPI nor chooses a caller protocol.
The runtime remains responsible for projections and unsupported pivot filtering.

## Final SDK output

```python
from agent_framework import AgentResponse, Content, Message
from ygo74.agent_runtime.integrations.agentframework import (
    AgentFrameworkOutputAdapter,
    ConversionStatus,
)

response = AgentResponse(messages=Message("assistant", [
    Content.from_text("Hello"),
    Content.from_uri("https://example.test/image.png", media_type="image/png"),
]))
converted = AgentFrameworkOutputAdapter().convert(response)
for decision in converted.decisions:
    if decision.status is not ConversionStatus.CONVERTED:
        print(decision.native_type, decision.status, decision.reason)
output = converted.output  # Return this AgentOutput from your runtime handler.
```

An actual configured SDK agent uses the same adapter:
`converted = adapter.convert(await agent.run(prompt))`.
Every content in every response message is visited, including tool messages;
conversion never relies on `.text` alone.

## Streaming SDK output

Create **one stream adapter per invocation**. Inspect each update conversion;
one native update can produce several pivot events. Feed these events to your
runtime handler's asynchronous iterator:

```python
from collections.abc import AsyncIterator
from agent_framework import BaseAgent
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent
from ygo74.agent_runtime.integrations.agentframework import (
    AgentFrameworkStreamAdapter,
    ConversionStatus,
)

async def stream_agent(agent: BaseAgent, prompt: str) -> AsyncIterator[AgentStreamEvent]:
    adapter = AgentFrameworkStreamAdapter()
    async with agent.run(prompt, stream=True) as updates:
        async for update in updates:
            converted = adapter.convert_update(update)
            for decision in converted.decisions:
                if decision.status is not ConversionStatus.CONVERTED:
                    print(decision.native_type, decision.status, decision.reason)
            for event in converted.events:
                yield event
    for event in adapter.finish():
        yield event
```

The application configures `agent` and its provider, credentials and policies.
Exceptions and cancellation propagate; do not call `finish()` in `finally` and
accidentally announce success after an abort. Native finish reasons may belong
to intermediate tool rounds, so only `finish()` emits a terminal. It closes
open contents, emits exactly one terminal, and is idempotent. A developer can
provide an explicit `Termination`; a detected SDK failure cannot be overwritten
with success. Subsequent updates are rejected.

Text/reasoning streams use native message/content identity when available.
For identity-less SDK updates, position within the update is the fallback; the
producer must keep positions stable for each text item. Tool argument strings
are **deltas**, correlated by call ID (including parallel calls), never parsed
as JSON before completion. Mapping arguments are complete JSON values.
Do not pass an aggregated final response back through the streaming adapter:
that would repeat content already emitted.

## Selection and supported content

| SDK content | Conversion |
| --- | --- |
| `text` | Final text or correlated text deltas |
| `function_call`, `function_result` | Typed tools; **internal observation by default**, never an automatic client execution request |
| `text_reasoning` | Excluded by default; `expose_reasoning=True` is a deliberate developer disclosure decision; protected content is **always excluded** |
| image `uri` / base64 `data` | URI or encoded media, preserving MIME without downloading |
| audio `uri` / base64 `data` | WAV, MP3, PCM16, FLAC, OPUS, AAC when exact MIME identifies format |
| `usage` / final `usage_details` | Genuine input/output counts, optional total, cache-read and reasoning counts; missing values are not filled with invented zeros |
| `error` | Failed termination; provider error details and raw representation are not copied |
| `stop`, `tool_calls` | Successful completion when the caller finishes the invocation |
| `length`, `content_filter` | Incomplete termination |
| unknown content/finish reason | Inspectable unsupported decision; unknown finish is incomplete |

SDK tool results do not carry a function name: the adapter reuses earlier call
identity within the invocation. Orphan results are unsupported, not assigned an
invented name. Canonical result `items` are all inspected: text items are joined,
while non-text tool-result items are explicitly unsupported (no hidden media
loss). Tool errors, non-JSON arguments/results, hosted files, provider tool
types, structured `response.value`, and non-image/audio media are inspectably
unsupported. User/system/developer messages are deliberately excluded.

Opaque metadata, protected reasoning, provider-specific billing counters,
transcription/codec assumptions, and `raw_representation` are not automatically
exposed. Native annotations/citations produce an explicit
`unsupported_annotations` decision while retaining the associated text; citation
offsets are not guessed. Unified SDK media contents are complete items; this adapter does not
invent audio chunk sequence/transcription correlation from arbitrary metadata.
No transcoding, URI fetching, or guessing missing MIME occurs.

`ConversionDecision` records native type, generated identity, status and an enum
reason, **not native payloads**. The caller can reject unsupported output, select
native events before conversion, or deliberately emit the core `Notification`
type. Unsupported data is never silently stringified as an answer.
`tool_execution=ToolExecution.CLIENT` is available only when the developer
intentionally delegates these calls to the client.

Conversion into the pivot does **not** guarantee projection onto an HTTP surface.
In runtime 1.0, internal tools/results and assistant images are filtered on all
surfaces. Exposable reasoning is projected only as a Responses summary. Audio
URI references and streaming audio are filtered; non-streaming Chat audio needs
encoded data and a genuine expiry. This adapter does not invent that expiry.
The runtime logs these projection limitations independently of the SDK conversion
decisions; text and deliberately client-executed tool calls are supported across
all three surfaces.

SDK 1.18 `UsageDetails` standardizes `cache_read_input_token_count` and
`reasoning_output_token_count`. These map respectively to the neutral
`TokenUsage.cached_input_tokens` and `reasoning_output_tokens` fields. Explicit
native zero remains zero; an absent or `None` value remains unknown (`None`).
SDK 1.18 does **not** standardize `cache_write_input_token_count`.
Consequently `cache_write_input_tokens` remains `None`; the adapter does not
infer it from the distinct `cache_creation_input_token_count` field or invent zero.
Streaming usage reports are accumulated from genuine
counts; if any report omits an optional counter, its cumulative value remains
unknown rather than treating that report as zero. Final `usage_details` takes
precedence over message usage contents to avoid double-counting.
Incomplete wire usage is filtered explicitly by the runtime when a surface
requires details that were not supplied; adapters never invent those details.

Anthropic requires genuinely known input/output counts in its final message and
initial `message_start`. An output without those counts fails explicitly with
`unsupported_output_projection`. Streaming handlers must emit a native usage
update that converts to `UsageEvent` **before any visible content**; later usage
events may update cumulative counts. Many real SDK providers report usage only
at the end. A developer-owned producer can yield
`UsageEvent(TokenUsage(0, 0, 0))` **before any backend/model execution**, when that
fresh invocation's observed consumption is genuinely empty, then forward actual
native cumulative usage. Neither the runtime nor this adapter supplies or assumes
that baseline. If execution occurred but final counters remain unknown, the caller
must fail/report the limitation rather than treat the initial baseline as final
consumption. Streams without genuinely known initial usage cannot be exposed
truthfully through Anthropic; the adapter does not buffer content to conceal
this limitation. OpenAI streaming behavior is unchanged. The offline example
truthfully reports zero because it never performs model inference.

## Reuse and verification

The integration reuses the core `AgentOutput`, media sources, JSON union,
`Termination`, usage, and streaming event types. It does not define a competing
pivot. A single content mapper serves final and streaming adapters; the latter
alone owns invocation-local correlation.

The [offline runnable example](../examples/python-agentframework-fastapi/README.md)
uses real SDK types and `HostingFactory`, with no inference credentials. Its tests
cover all three HTTP surfaces in both modes. Integration fixtures cover selection,
tools, media, usage and parallel argument fragments. This Python-first integration
does not claim .NET/Java parity.

Official API references:
[Running agents](https://learn.microsoft.com/en-us/agent-framework/agents/running-agents?pivots=programming-language-python)
and [Microsoft Agent Framework](https://github.com/microsoft/agent-framework).

Definitive runtime references:
[typed output contract and support matrix](../../specs/001-openai-endpoint-exposure/contracts/typed-output-contract.md)
and [output snapshot schema v2](../../specs/001-openai-endpoint-exposure/contracts/agent-output-v2.schema.json).
The schema describes complete serialized snapshots; handlers still return typed
objects, not raw dictionaries.

# LangChain output integration

Return to the [Python documentation entry point](README.md).

## Installation and ownership

```powershell
python -m pip install "ygo74-agent-runtime-langchain==1.0.0"
```

Requires Python 3.12+, `ygo74-agent-runtime-agents>=1.0.0,<2`, and
`langchain-core>=1.6.3,<1.7`. The integration is tested offline against
**langchain-core 1.6.3 and 1.6.6** in dedicated validation virtual environments.
Only `langchain-core` is needed for these adapters. Install `langchain` and your
model/provider SDK separately if your application needs them.

The wheel owns only `ygo74.agent_runtime.integrations.langchain`, including its
`py.typed` marker. It does not own shared namespace files, depend on FastAPI or
provider SDKs, or add LangChain dependencies to the agents distribution.

Reuse decision: the integration consumes the agents distribution's `AgentOutput`,
contents, media sources, usage, termination and `AgentStreamEvent` types directly.
It uses LangChain's standardized `content_blocks`, concrete message/result classes,
and `StreamEvent` schema; it does not define a competing output contract or
interpret endpoint protocols.

## Final results: runnable offline example

```python
from langchain_core.messages import AIMessage
from ygo74.agent_runtime.integrations.langchain import LangChainResultAdapter

native = AIMessage(
    content="A local answer.",
    usage_metadata={
        "input_tokens": 2, "output_tokens": 4, "total_tokens": 6,
        "input_token_details": {"cache_read": 1, "cache_creation": 1},
        "output_token_details": {"reasoning": 2},
    },
)
converted = LangChainResultAdapter().convert(native)
assert converted.output is not None
assert converted.output.contents[0].text == "A local answer."
assert converted.output.usage is not None
assert converted.output.usage.cached_input_tokens == 1
assert converted.output.usage.reasoning_output_tokens == 2
assert converted.output.usage.cache_write_input_tokens == 1
print(converted.output)
```

`convert()` accepts SDK `AIMessage`, `ToolMessage`, `ChatGeneration`,
`ChatResult`, and single-prompt `LLMResult`. Input messages are intentionally
excluded. A result with multiple candidates requires the developer's choice:
`convert(result, generation_index=1)` selects the second candidate. Batched
`LLMResult` objects must first be split into a single prompt result.
For a LangChain agent state, explicitly select an SDK message from the state in
your application, then convert it; the integration does not guess dictionary
shapes or turn tool artifacts into client output.

`converted.output` can be returned from a runtime handler. Inspect the conversion
status and diagnostics first, especially when unsupported portions are present.
`finish_reason` metadata of `length`, `max_tokens` or `content_filter` becomes
incomplete termination for both final results and streaming snapshots. The
original reason is preserved; other finish reasons remain successful without
inventing usage.

## Streaming: runnable offline example

```python
import asyncio

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from ygo74.agent_runtime.domains.contracts.stream_events import TerminalEvent, TextDelta
from ygo74.agent_runtime.integrations.langchain import (
    ConversionStatus,
    LangChainStreamAdapter,
)


async def main() -> None:
    model = FakeListChatModel(responses=["hello"])
    adapter = LangChainStreamAdapter()  # One instance per invocation.
    answer: list[str] = []
    terminals = 0
    async for native in model.astream_events("question", version="v2"):
        # Selection is your policy, not a protocol-specific decision.
        if native["event"] not in ("on_chat_model_stream", "on_chat_model_end"):
            continue
        converted = adapter.convert(native)
        assert converted.status is not ConversionStatus.UNSUPPORTED
        for pivot in converted.events:
            # In a handler's async generator, yield pivot instead.
            if isinstance(pivot, TextDelta):
                answer.append(pivot.text)
            if isinstance(pivot, TerminalEvent):
                terminals += 1
    assert "".join(answer) == "hello"
    assert terminals == 1
    print("".join(answer))


asyncio.run(main())
```

This fake SDK model reports no token usage. It demonstrates neutral conversion,
not a successful all-surfaces HTTP response. Anthropic requires genuine
input/output counts for final responses and an initial `UsageEvent` before
visible streamed content. An unknown-usage response or stream is explicitly
rejected by that runtime projection; OpenAI can still represent it without usage.
The integration forwards unknown-usage content immediately, without buffering
or inventing counters. If the SDK provides usage and content together, the
converter places the genuine usage event first. An application may also emit a
genuinely known initial usage event before consuming native content.
Before any backend/model execution, a developer-owned producer may truthfully
emit `UsageEvent(TokenUsage(0, 0, 0))` for its empty observed invocation. The
adapter never assumes or generates this baseline. Once a backend executes,
unknown final counters must be reported as a limitation/failure; the old empty
baseline must not be presented as known final consumption. A genuinely local,
no-model echo may retain its real zero counts.

Use **`astream_events(..., version="v2")`**, not v1 or v3. Root identity relies on
v2's `parent_ids`. Select events by your own names/tags/metadata policy before
calling the converter; never share an adapter between concurrent invocations.
For direct SDK chunk iteration use `convert_chunk(chunk, run_id="your-model-run")`.

Each native event maps to zero or multiple pivot events. SDK chat deltas open
content once, emit typed text/reasoning or tool-argument deltas, and close content
on model end. Aggregated `AIMessageChunk` end snapshots are converted using the
SDK's `message_chunk_to_message()`. Already streamed content is not replayed;
new final media or complete calls may still be emitted. Input and chain stream
snapshots are excluded to avoid duplicate answers.

Usage events contain cumulative counts across selected model runs. Stream chunk
usage is accumulated according to SDK chunk semantics; a final usage snapshot
replaces that run's counts instead of adding them again. The pivot currently
preserves SDK input/output/total counts and, when genuinely supplied,
`input_token_details["cache_read"]` as `cached_input_tokens` and
`input_token_details["cache_creation"]` as `cache_write_input_tokens`, plus
`output_token_details["reasoning"]` as `reasoning_output_tokens`.
Explicitly reported zero counts stay zero; absent details stay `None`.
Cache-read and cache-write counts are never inferred from each other.
Cumulative optional fields are summed only when every contributing usage delta
or run supplies that field. Otherwise they remain unknown until a genuine final
SDK snapshot provides complete per-run counts. Totals are never inferred from
input/output counts or replaced with fabricated zero values. Audio-token
breakdowns are not mapped. Runtime projections may filter usage
missing protocol-required fields rather than manufacture counters.

Root chat-model end, root tool end, or root chain end emits one terminal event.
If your selection omits the root end, yield the events from `adapter.finish()`
after successful iteration. For incomplete or failed execution explicitly call
`finish(Termination(...))`; use the core `ErrorEnvelope` for a failure.
The SDK raises execution failures rather than supplying an `on_*_error` event
in v2, so application exception/cancellation handling remains developer-owned.
Do not call a successful `finish()` in a `finally` block after an exception.
An adapter emits nothing further after termination.

## Tools, reasoning, media and developer decisions

- Model tool calls default to `ToolExecution.INTERNAL`, appropriate for an agent
  that executes its own tools. Set `tool_execution=ToolExecution.CLIENT` only for
  calls the client must execute. Server-tool blocks and `on_tool_start/end`
  execution observations always remain internal.
- Tool-call chunks require an SDK index for parallel correlation. Argument
  fragments remain raw strings; they are never parsed as partial JSON.
  Missing initial call ID/name may be buffered until SDK metadata arrives.
  Changing an established name/ID or ending without them is an invalid lifecycle.
- Tool execution observations use the SDK tool `run_id` as their invocation
  identity. Pass `tool_call_id=` to `convert()` when your application knows the
  corresponding model call ID. Select the corresponding start and end.
  Select either declarations or execution observations when you do not want both.
- `ToolMessage` content is preserved as JSON; its private `artifact` is not exposed.
  The pivot requires a genuine nonempty tool name. A standalone `ToolMessage`
  without one is `UNSUPPORTED`, with no output content. Standardized server-tool
  results recover their name by matching the call ID to native calls in the same
  message or correlated streamed call metadata. Orphan results are explicitly
  unsupported and omitted; names are never fabricated. The pivot has no per-tool
  failure field, so SDK error-status tool results are returned with an inspectable
  unsupported diagnostic rather than falsely reporting success.
- Reasoning is excluded unless `expose_reasoning=True`. This setting is an
  explicit assertion that the developer is allowed to publish the SDK's reasoning
  text. Opaque/encrypted reasoning without text is unsupported, not decrypted or
  relabeled as the answer.
- Standardized text citations map to core `UrlCitation` only when the SDK supplies
  a genuine URL, title and both offsets. Unsupported citation forms are diagnosed
  without inventing fields. Final results preserve these annotations. Streaming
  preserves citations known at content start (offsets may target the completed
  text); annotations arriving later are explicitly unsupported because the
  neutral stream currently has no amendment event. Text is never replayed to
  simulate an annotation update.
- Standardized image/audio blocks require an explicit MIME type plus URI or
  base64. Images support either source. Audio supports known WAV, MP3, FLAC,
  Opus and AAC MIME types. No download, transcoding or codec guessing occurs.
  Ambiguous PCM MIME types, provider file IDs and unknown formats are unsupported.
  SDK audio block IDs are preserved; absent IDs use a local content identity.
- Standardized audio blocks do not define an audio-byte-delta/transcript
  correlation contract. Therefore complete media in incremental chunks is
  explicitly unsupported; final standardized media snapshots are supported.
  Provider-specific audio deltas, transcriptions and extras need an explicit
  application mapping to the core audio events, not an inferred mapping here.
- Adapter support means a valid neutral content, not guaranteed endpoint
  representation. The runtime owns projection decisions and correlated filtering
  diagnostics. In particular, the current runtime filters assistant images and
  streamed/URI audio; encoded Chat audio requires a real expiry value, which
  standardized SDK audio blocks do not supply. The adapter never fabricates one.
- Unknown/custom native events and unknown content blocks return `UNSUPPORTED`
  with payload-free diagnostics. Developer code can ignore them or deliberately
  produce `adapter.notification("Selected progress", content_id="notice-1")`.
  A notification is a pivot `Notification`, never a fabricated response string.

`ConversionOutcome.status` is `CONVERTED`, `EXCLUDED`, or `UNSUPPORTED`.
`events`, `output`, and `diagnostics` are typed and inspectable. A partially
supported result retains its supported contents/events with `UNSUPPORTED`;
inspect all diagnostics rather than treating that status as an empty result.
Invalid JSON values and invalid stream sequencing raise
`LangChainConversionError`, not a support-limitation result.

SDK references:
[standardized messages](https://reference.langchain.com/python/langchain-core/messages/),
[AIMessageChunk](https://reference.langchain.com/python/langchain-core/messages/ai/AIMessageChunk),
[v2 streaming events](https://reference.langchain.com/python/langchain-core/runnables/base/Runnable/astream_events).

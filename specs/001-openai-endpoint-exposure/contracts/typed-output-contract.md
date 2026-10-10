# Provider-neutral typed output contract v2

This is the definitive contract for Python agents distribution **1.0.0**. It is
independent of the historical Standard Exchange v1 schema. Requests, normalized
handler request dictionaries, provider options, routes, authentication, HTTP status
mapping, discovery and HostingFactory configuration are unchanged. .NET/Java
implementation of this output amendment is deferred; Python tests do not establish
cross-language parity.

**Anthropic streaming prerequisite:** the developer-owned producer supplies a
genuinely observed UsageEvent. The Python native-hosting pilot can buffer
converted content frames until late usage arrives; this delays visibility while
preserving order. No usage at completion still fails explicitly. Before **any** backend/model
execution, an observed empty invocation may be declared as
`UsageEvent(TokenUsage(0, 0, 0))`; subsequent native cumulative snapshots replace
that baseline. This is not a guessed final count. Offline/no-LLM echo producers can
truthfully report zero consumption. The runtime never supplies this baseline
itself; producers with no usage fail explicitly rather than emit a malformed
message_start. Both later input and output counts are retained in message_delta.

## Public API and schema scope

Import public types from `ygo74.agent_runtime.domains.contracts`. Models are
dataclasses; new content/output/event classes are frozen and slotted. Python
concrete class identity discriminates the content/event unions. There is **no
`type` or `kind` field** in these constructors and no heuristic dictionary decoding.
When exporting neutral JSON, `AgentOutputSerializer` preserves that identity with
explicit `{ "type": "<tag>", "value": { ...exact fields... } }` boundary wrappers.

[`agent-output-v2.schema.json`](agent-output-v2.schema.json) describes complete
tagged serialized values, using the exact Python field names inside `value`.
`AgentOutputSerializer().serialize(output)` recursively tags content, media-source,
event and output unions, converts tuples to JSON arrays and enums to strings, and
retains absent optional values as `null`. All declared fields, including constructor
defaults, are present in this complete schema shape. Plain `dataclasses.asdict`
does not preserve union identities and is **not the canonical serialization**.
This is a validation/reference representation, **not a newly accepted handler
dictionary format or an additional HTTP protocol**.

The root validates `TaggedAgentOutput`. Named `$defs` retain exact record fields
and separate `Tagged<ClassName>` wrappers. `AgentContent`, `MediaSource` and
`AgentStreamEvent` use `oneOf` over wrappers with distinct constant tags. Thus
ContentEvent and ContentStart, and TextDelta and AudioTranscriptDelta, cannot
collapse even when their `value` fields match. Notification is never inferred as
answer text. The handler runtime still accepts typed instances, not these JSON
snapshots. Lifecycle validation belongs to the runtime, not JSON Schema.

The public `OutputValueType` enum fixes the tags:

| Classes | Tags in the same order |
|---|---|
| AgentOutput, StandardExchangeResponse | `agent_output`, `exchange_response` |
| TextContent, Notification, ReasoningContent | `text`, `notification`, `reasoning` |
| ToolCallContent, ToolResultContent, ImageContent, AudioContent | `tool_call`, `tool_result`, `image`, `audio` |
| MediaUri, EncodedMedia | `media_uri`, `encoded_media` |
| ContentEvent, ContentStart, TextDelta, ToolArgumentsDelta | `content_event`, `content_start`, `text_delta`, `tool_arguments_delta` |
| AudioDelta, AudioTranscriptDelta, ContentEnd, UsageEvent, TerminalEvent | `audio_delta`, `audio_transcript_delta`, `content_end`, `usage_event`, `terminal_event` |

TokenUsage, Termination, ErrorEnvelope and UrlCitation are non-union records and
retain their ordinary fields without wrappers. Dictionaries inside genuine JSON
arguments, results or metadata are ordinary JSON, never heuristically decoded.
The serializer rejects untyped root values and non-JSON values with
`OutputSerializationError`. It does not validate producer ordering or add an HTTP
route, deserialize raw handler outputs, or change any provider projection.

For example:

```python
serializer = AgentOutputSerializer()
serializer.serialize(Notification("working"))
# {"type": "notification", "value": {"text": "working"}}
serializer.serialize(TextContent("working"))
# {"type": "text", "value": {"text": "working", "annotations": []}}
serializer.serialize(ContentEvent("answer", TextContent("answer")))["type"]
# "content_event"
serializer.serialize(ContentStart("answer", TextContent("answer")))["type"]
# "content_start"
```

## Exact constructors

Defaults below are constructor defaults; omitted fields are still emitted by
`dataclasses.asdict`. `JsonValue` is finite, acyclic JSON: null, boolean, number,
string, array or string-keyed object.

| Type | Fields, in constructor order |
|---|---|
| `AgentOutput` | `contents: tuple[AgentContent, ...] = ()`, `usage: TokenUsage \| None = None`, `termination: Termination = Termination()` |
| `TextContent` | `text: str`, `annotations: tuple[UrlCitation, ...] = ()` |
| `Notification` | `text: str` |
| `ReasoningContent` | `text: str`, `exposable: bool = False` |
| `ToolCallContent` | `call_id: str`, `name: str`, `arguments: JsonValue = {}`, `execution: ToolExecution = CLIENT` |
| `ToolResultContent` | `call_id: str`, `name: str`, `result: JsonValue`, `execution: ToolExecution = INTERNAL` |
| `ImageContent` | `source: MediaSource` |
| `AudioContent` | `source: MediaSource`, `audio_id: str`, `transcript: str \| None = None`, `format: AudioFormat = WAV`, `expires_at: int \| None = None` |
| `UrlCitation` | `url: str`, `title: str`, `start_index: int`, `end_index: int` |
| `MediaUri` | `uri: str`, `mime_type: str` |
| `EncodedMedia` | `data: str`, `mime_type: str` |
| `TokenUsage` | `input_tokens: int`, `output_tokens: int`, `total_tokens: int \| None = None`, `cached_input_tokens: int \| None = None`, `reasoning_output_tokens: int \| None = None`, `cache_write_input_tokens: int \| None = None` |
| `Termination` | `status: TerminationStatus = SUCCESS`, `reason: str \| None = None`, `error: ErrorEnvelope \| None = None` |
| `ErrorEnvelope` | `code: str`, `category: str`, `message: str`, `details = None`, `request_id: str \| None = None`, `retryable: bool \| None = None` |
| `StandardExchangeResponse` | `request_id: str`, `status: str`, `output: AgentOutput \| None = None`, `error: ErrorEnvelope \| None = None`, `metadata: dict = {}` |

Mutable defaults shown above are constructed independently using default factories,
not shared dictionaries. `ErrorEnvelope` and `StandardExchangeResponse` reuse the
existing mutable/slotted envelope types; their fields are not new content classes.
`ErrorEnvelope.details` remains the existing Python `Any` field; JSON snapshots must
contain JSON-serializable details. Categories reuse existing shared errors, including
validation, authentication, authorization, routing, mapping, projection and handler execution.

`AgentContent` is the union of TextContent, Notification, ReasoningContent,
ToolCallContent, ToolResultContent, ImageContent and AudioContent. `MediaSource` is
MediaUri or EncodedMedia.

Enums:

- `ToolExecution`: `INTERNAL = "internal"`, `CLIENT = "client"`.
- `TerminationStatus`: `SUCCESS = "success"`, `INCOMPLETE = "incomplete"`,
  `FAILED = "failed"`.
- `AudioFormat`: `WAV = "wav"`, `MP3 = "mp3"`, `PCM16 = "pcm16"`,
  `FLAC = "flac"`, `OPUS = "opus"`, `AAC = "aac"`.

## Handler results and stream events

Handlers return an `AgentOutput` directly or through an awaitable. They may also
return `StandardExchangeResponse(status="success", output=AgentOutput(...))`, or
`status="error"` with an ErrorEnvelope and no output. Wrapped `request_id` must
match the invocation. This Python wrapper convenience does not claim that the old
v1 output schema describes the new semantics.

`AgentResult` and `AgentInvocation` are declared in
`domains.handlers.handler_protocol`: final results or `AsyncIterable[AgentStreamEvent]`,
optionally awaited. The FastAPI entrypoint continues to receive its existing
normalized request dictionary.

The existing `domains.endpoints.conversation_payloads.AgentReplyRenderer.to_payload`
returns a typed StandardExchangeResponse preserving `AgentReply.output` when
provided, otherwise `AgentOutput((TextContent(reply.text),))`. Its request_id,
route_key and pending_confirmations metadata are preserved. Conversation request
reading, principal resolution and approval/session behavior are unchanged.

| Event | Fields, in constructor order |
|---|---|
| `ContentEvent` | `content_id: str`, `content: AgentContent` — one complete content |
| `ContentStart` | `content_id: str`, `content: AgentContent` — opens incremental content |
| `TextDelta` | `content_id: str`, `text: str` |
| `ToolArgumentsDelta` | `content_id: str`, `delta: str` |
| `AudioDelta` | `content_id: str`, `data: str`, `sequence: int` |
| `AudioTranscriptDelta` | `content_id: str`, `text: str` |
| `ContentEnd` | `content_id: str` |
| `UsageEvent` | `usage: TokenUsage` |
| `TerminalEvent` | `termination: Termination = Termination()` |

`AgentStreamEvent` is precisely the union of those nine classes.

Rules:

1. Each content identity is nonempty and unique per invocation. A ContentEvent is
   already closed. ContentStart must precede deltas and ContentEnd. No delta or
   second end may target a closed/unknown identity. Tool call identities and audio
   identities are also unique. Interleaved content retains independent state.
2. TextDelta targets TextContent, Notification or ReasoningContent. Initial text
   plus deltas becomes the completed shared content. Notifications are excluded
   from non-streaming business output. Streaming projects them as text, including
   the final Responses wire snapshot so emitted coordinates, IDs and output_text
   stay coherent. Internal StreamState.output may remain notice-free for business
   consumers; it is not the Responses streaming wire snapshot.
3. ToolArgumentsDelta targets ToolCallContent whose initial arguments are `{}`.
   Concatenate nonempty fragments; parse JSON only at ContentEnd. An empty delta
   is a no-op. A complete ContentEvent may carry already parsed arguments.
   The runtime never executes tools. Observed framework tools should explicitly
   use INTERNAL; CLIENT means a call that the caller is asked to execute.
4. AudioDelta targets encoded AudioContent, not a URI source. Each fragment is
   independently base64 encoded. Sequence starts at zero and is contiguous within
   that audio identity. AudioTranscriptDelta targets AudioContent and carries
   associated transcription. MIME must match image/audio kind. No downloading,
   codec guessing, resampling or transcoding occurs.
5. UsageEvent supplies a cumulative snapshot; the latest snapshot is authoritative.
   Counters must be nonnegative integers (not booleans). If supplied, total_tokens
   cannot be smaller than input_tokens + output_tokens. Unknown counters are
   never estimated from text, tools or notifications. cached_input_tokens represents
   genuinely observed cache-read input tokens, not cache creation; reasoning_output_tokens
   is a genuinely observed output-token breakdown. cache_write_input_tokens is a
   genuinely observed count of input tokens written into the cache. `None` means unknown; explicit
   zero is a known count. These optional fields preserve existing constructors.
   Chat usage requires known total_tokens; otherwise the complete usage object is
   omitted with incomplete_usage diagnostic. Responses requires known total_tokens,
   cached_input_tokens, reasoning_output_tokens and cache_write_input_tokens; otherwise usage is `null` with
   the same diagnostic. No missing count or total is fabricated.
   Anthropic requires known base input/output counts in every successful Message
   and message_start; absent usage is a projection failure, not optional metadata.
6. Every incremental producer must yield TerminalEvent. Success/incomplete require
   all content closed; failure may terminate open content and requires ErrorEnvelope.
   Only failure may carry an error. Runtime-assigned sequence numbers, wire indices
   and response IDs do not appear in the pivot.
7. The runtime stops and closes the producer before emitting the terminal. It never
   consumes later producer events or emits success after failure. Producer failure,
   invalid values/order and missing terminal yield explicit errors, not filtering.
   Cancellation/disconnection propagates and closes the producer without fabricating
   completion.
8. Citation offsets are nonnegative character indices into completed TextContent;
   start_index ≤ end_index ≤ text length. URL must be absolute HTTP/HTTPS.
   Incremental content may carry citations whose bounds become valid only after
   text deltas; final bounds are checked at ContentEnd.

Schema catches structural constraints. Counter relationships, citation bounds,
base64 validity (`contentEncoding` is an annotation), identities, fragment order,
JSON finiteness and stream termination are enforced by the typed runtime.

## Tested protocol support matrix

“Filter” means omit that content/annotation without converting it to response text,
and emit a safe correlated diagnostic. No hosted/provider tool event is invented.

| Pivot | Chat final | Chat stream | Responses final | Responses stream | Anthropic final | Anthropic stream |
|---|---|---|---|---|---|---|
| TextContent | assistant text | content delta | output_text | output_text lifecycle | text block | text block/delta |
| Notification | filter | text delta | filter | text lifecycle and final wire snapshot | filter | text block/delta |
| Reasoning, exposable=false | filter | filter | filter | filter | filter | filter |
| Reasoning, exposable=true | filter | filter | reasoning summary | summary lifecycle | filter (no invented signature) | filter |
| CLIENT tool call | function tool_calls | correlated argument deltas | function_call | correlated function-call lifecycle | tool_use, object arguments only | tool block after complete argument validation |
| INTERNAL tool call | filter | filter | filter | filter | filter | filter |
| ToolResultContent, either execution | filter | filter | filter | filter | filter | filter |
| Image URI or encoded | filter | filter | filter | filter | filter | filter |
| Audio URI | filter | filter | filter | filter | filter | filter |
| Encoded audio, known expires_at | one assistant audio object, original bytes | filter | filter | filter | filter | filter |
| Encoded audio, unknown expires_at | filter | filter | filter | filter | filter | filter |
| UrlCitation on TextContent | annotation filtered; text retained | annotation filtered; text retained | url_citation annotation | annotation.added + completed content/snapshot | annotation filtered; text retained | annotation filtered; text retained |
| TokenUsage, total known | usage; optional genuinely known details | same terminal usage | only if all required breakdowns known | same terminal snapshot rule | known input/output counts | message_start and message_delta counts |
| TokenUsage, total unknown | omit with incomplete_usage diagnostic | same | usage=null with diagnostic | same | known input/output counts | message_start and message_delta counts |
| No TokenUsage | omit | omit | usage=null | usage=null | explicit projection failure | explicit failure before visible content or successful terminal |

Chat maps genuine cached/cache-write/reasoning counters to optional
prompt_tokens_details.cached_tokens, prompt_tokens_details.cache_write_tokens
and completion_tokens_details.reasoning_tokens. Responses emits mandatory
input_tokens_details.cached_tokens, input_tokens_details.cache_write_tokens and
output_tokens_details.reasoning_tokens only when all and total_tokens are known.
OpenAI SDK 3.24.0 requires cache_write_tokens as an integer too, not nullable; it
cannot honestly be filled with zero when unknown. Anthropic always projects the known base
input/output counts; genuinely known cached_input_tokens additionally maps to
cache_read_input_tokens, and genuinely known cache_write_input_tokens maps to
cache_creation_input_tokens. Neither a cache-creation counter nor an Anthropic reasoning breakdown
is invented. Usage filtering is independent of content filtering and applies to
non-streaming and streaming terminal snapshots alike where usage is optional.

### Anthropic mandatory usage boundary

Anthropic successful Messages require `usage.input_tokens` and
`usage.output_tokens`; message_start requires that same Message envelope, and
message_delta requires usage.output_tokens. The runtime cannot omit these fields
or invent zero. Final AgentOutput without usage raises
`domains.mapping.output_projector.OutputProjectionError`
(`unsupported_output_projection`, category `projection`); HTTP invocation returns
500 with an explicit error rather than a malformed successful Message.

Incremental producers must supply a genuinely observed UsageEvent **before any
supported visible content**, including notifications and client tools. Its counts
seed message_start. Later cumulative snapshots update message_delta.
Both `input_tokens` and `output_tokens` are projected in the delta so the native
SDK final Message reflects the latest snapshot, not just its initial baseline.
This baseline-to-updated-input path requires an SDK that handles input_tokens in
message_delta; the native client regression is verified against Anthropic 1.11.0.
An empty invocation baseline `UsageEvent(TokenUsage(0, 0, 0))` is valid when the
developer emits it before any backend/model execution; subsequent native usage
must replace it. Offline producers that make no model calls can truthfully retain
zero. A baseline is never automatically manufactured by the runtime.
If model execution occurs but final counters remain unknown, the producer must
report that limitation/failure rather than present its earlier empty baseline as
known final consumption. The runtime trusts explicit typed snapshots; it cannot
infer backend execution or token consumption from visible content.
Completed AgentOutput results, including awaited/wrapped results, emit their known usage
before content automatically. If usage is absent when visible content arrives,
the runtime closes the producer and emits one native error event, without
message_start, message_stop or reading ahead for late usage. No entire stream is
buffered. A success/incomplete terminal without known usage likewise fails.
Failed terminals and producer errors can be emitted without a Message envelope.
SDK integrations that only receive native usage after text can expose incremental
Anthropic output if their developer-owned producer reports the genuinely empty
baseline before backend execution and then forwards native usage snapshots.
Otherwise use a completed result with genuinely known usage or explicitly accept
this projection limitation. Producers must not infer a zero baseline after model
execution, or estimate unknown final counts merely to satisfy this boundary.

Only the first supported audio content is included in a Chat final; additional
audio outputs are filtered explicitly. All six AudioFormat values are carried
without conversion; source bytes and MIME are developer-owned. The runtime does
not fabricate an expiry, transcript, hosted image-generation tool or hosted MCP
call. Unsupported media remains valid pivot content and is deliberately filtered.

Anthropic tool argument fragments are retained until ContentEnd because an array
is valid pivot JSON but not a valid Anthropic tool input. Such a completed tool is
filtered before a block is opened, avoiding orphan blocks. This does not buffer
the entire stream or delay unrelated text deltas.

Termination mapping:

| Status | Chat | Responses | Anthropic |
|---|---|---|---|
| SUCCESS | stop, or tool_calls when applicable; `[DONE]` | response.completed | end_turn, or tool_use; message_stop |
| INCOMPLETE | content_filter when reported, otherwise length; `[DONE]` | response.incomplete; canonical known reason or incomplete_details=null | known budget aliases → max_tokens, otherwise stop_reason=null; message_stop |
| FAILED | error; `[DONE]`, no successful finish | response.failed | error, no message_stop success |

Final and streamed projectors share the same native reason translation.
The source/canonical aliases `length`, `max_tokens` and `max_output_tokens` mean a
token budget: Chat uses `length`, Responses uses `max_output_tokens`, and Anthropic
uses `max_tokens`. `content_filter` stays `content_filter` in Chat and Responses.
Anthropic has no equivalent content_filter reason; it is omitted as optional
stop_reason=null rather than invented as a token limit or refusal.
For Responses, absent or unrecognized reasons produce incomplete_details=null;
arbitrary free-text pivot reasons never enter its native literal field. Supplied
unrecognized/unrepresentable reasons produce a safe correlated
unsupported_termination_reason diagnostic, without logging their value.
Chat retains its required generic INCOMPLETE → length fallback when no recognized
source reason is available. Successful tool/stop and failed mappings are unchanged.

Responses and Anthropic do not emit the Chat `[DONE]` marker. Responses streaming
snapshots retain all emitted supported items at their assigned output indices,
including notifications converted to TextContent. Snapshot output_text is derived
from those wire contents. Failed snapshots retain open items as in-progress so
later closed items do not shift their indices. Non-streaming output still filters
and diagnoses notifications. All-filtered output
ends with an empty compliant business result and explicit diagnostic when the
producer's termination is successful and mandatory protocol metadata is available;
filtering never overrides failure.

Filtered logs include request_id, route_key, protocol, pivot type and reason code;
they exclude text, tool names/arguments/results, media bytes and sensitive URLs.
Relevant codes include notification_nonstream, internal_tool,
tool_result_not_assistant_output, reasoning_not_exposable, unsupported_reasoning,
unsupported_assistant_image, unsupported_audio, unsupported_streaming_audio,
audio_expiry_required, multiple_audio_outputs, unsupported_tool_arguments,
unsupported_citation, incomplete_usage, unsupported_termination_reason and
all_contents_filtered. Invalid output uses
invalid_agent_output; producer execution failure uses agent_execution_error.
Missing mandatory Anthropic usage uses unsupported_output_projection, with safe
request/route/protocol correlation and no output text in the diagnostic.

## Migration and validation

Raw strings, dictionaries, native OpenAIResponsesResult and native
OpenAIResponsesStreamEvent are not handler output contracts. Developers explicitly
construct TextContent for text/JSON rendered as text, Notification for progress,
and neutral tool/media events. Unknown native framework events are developer-owned:
ignore them or deliberately convert them into a Notification.

Schema tests are in `tests/contract/test_agent_output_v2_schema.py`. Exact fields,
union inventory and enums are checked against concrete dataclasses, and complete
output/event snapshots are validated with the existing JSON Schema tooling.
Projection and lifecycle matrices are exercised by:

- `tests/integration/python/test_neutral_outputs.py`
- `tests/integration/python/test_neutral_stream_lifecycle.py`
- `tests/integration/python/test_output_citations.py`
- `tests/integration/python/test_responses_notifications.py`
- `tests/integration/python/test_output_usage_sdk.py`
- `tests/integration/python/test_anthropic_usage_sdk.py`
- `tests/integration/python/test_openai_responses_api.py`
- `tests/contract/test_agent_output.py`
- `tests/performance/python/test_output_projection_budget.py`

The tests cover notification exclusion, safe diagnostics, interleaved tools/media,
argument fragments, URI/encoded media, transcripts, reasoning opt-in, usage,
terminal uniqueness, failure/cancellation/closure, empty output, concurrent state
and measured p95 overhead/first-delta budgets.

Real OpenAI SDK schema tests are optional (`pytest.importorskip("openai")`) so the
core distribution does not depend on or import the SDK. The validated developer
environment uses OpenAI SDK 3.24.0; to run this extra wire gate, install that SDK
in a developer/test environment and execute
`python -m pytest tests\integration\python\test_output_usage_sdk.py`.
It validates ChatCompletion, ChatCompletionChunk and Response models against both
complete genuinely known usage and filtered incomplete usage, including known zeros.
It also validates final/streamed length, max_tokens, max_output_tokens and
content_filter translation plus safely omitted unknown/absent Responses reasons.

Optional actual Anthropic SDK validation uses the installed SDK (validated with
1.11.0), without adding any SDK dependency/import to agents. Run
`python -m pytest tests\integration\python\test_anthropic_usage_sdk.py`.
It validates Message, RawMessageStartEvent and RawMessageDeltaEvent, exercises the
native async SDK streaming client through the ASGI endpoint, and proves unknown or
late usage produces explicit errors and closes the producer rather than malformed
wire envelopes. Its final/streamed reason tests also verify that token-limit aliases
translate correctly and unrepresentable reasons are not fabricated.

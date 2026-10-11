# Reference Agent (.NET, Microsoft Agent Framework)

A single-file-per-concern reference implementation of a **standard** Microsoft Agent Framework agent
(`ChatClientAgent`, built with `chatClient.AsAIAgent(...)`) exposed through every hosting surface
Microsoft documents for it. It exists as the framework-only baseline that an integration against
`ai-enterprise-agent-runtime` is written, and measured, against.

**This sample has no dependency on `ai-enterprise-agent-runtime`.** Nothing in `Program.cs`,
`Tools/`, `Middleware/`, or `Endpoints/` references `Ygo74.AgentRuntime.*`. That is deliberate: it
lets a reader see exactly which capabilities the framework provides on its own, before the runtime
library adds anything on top.

## Scope

**Included** - the standard agent type and its documented capabilities:

- A plain function tool (`get_weather`).
- A human-in-the-loop, approval-gated function tool (`send_weather_alert`, wrapped in
  `ApprovalRequiredAIFunction`).
- A **hosted MCP tool** (`HostedMcpServerTool`) against the public
  [Microsoft Learn MCP server](https://github.com/MicrosoftDocs/mcp): OpenAI's Responses API calls
  the remote MCP server itself, gated behind mandatory tool approval.
- A **hosted Code Interpreter** tool (`HostedCodeInterpreterTool`) - a provider-run Python sandbox.
- A **hosted File Search** tool (`HostedFileSearchTool`) over a vector store created at startup.
- An **Agent Skill** (`AgentInlineSkill`, via `AgentSkillsProvider`): a unit-converter skill bundling
  instructions, a data resource, and a runnable script.
- A **RAG context provider** (`TextSearchProvider`) over an in-memory FAQ (`Rag/FaqSearch.cs`) -
  the same mechanism a production retrieval integration uses, with a keyword match standing in for
  a real vector search.
- **Planning and Todos** (`TodoProvider` + `AgentModeProvider`) and **Agent Looping** (`LoopAgent` +
  `TodoCompletionLoopEvaluator`), exposed under the second `reference-agent-planner` route.
- **Structured Outputs**, via a `response_format`-forwarding `OpenAIChatCompletionsMapOptions` on
  the Chat Completions route.
- **Multimodal**, which needs no dedicated code: `ChatClientAgent` already accepts image/audio/file
  content in any incoming message.
- **OpenTelemetry observability** (`UseOpenTelemetry`, console exporter, optional OTLP).
- Three middleware layers: chat-client (`Middleware/ChatMiddleware.cs`, one call per model
  round-trip), agent-run (`Middleware/AgentMiddleware.cs`, one call per user turn), and
  function-invocation (`Middleware/AgentMiddleware.cs`, one call per tool call).
- Sessions / conversation continuity, handled by each hosting surface's own storage
  (`AddOpenAIConversations`, AG-UI's session store, A2A's `contextId`) - nothing custom is written
  for it in this sample.
- Streaming, supported natively by every hosting surface mapped below; nothing extra is required to
  enable it.
- Hosting over five documented surfaces (see below).

**Deliberately excluded / not achievable in this sample** (see the project's own concept pages
before assuming a gap):

- `Microsoft.Agents.AI.Harness` - a different, opinionated agent type with its own planning, TODO
  tracking, context compaction, file access/memory, and don't-ask-again approval. The user
  explicitly asked for the standard agent, not the harness agent.
- `Microsoft.Agents.AI.Workflows` - graph-based, multi-agent orchestration. This sample is
  single-agent by design.
- **Agent Hooks** - the hook/interceptor extensibility point documented for Agent Framework is
  currently Python-only (`agent_framework` core `Agent` hooks); no equivalent public API exists in
  the .NET packages as of this writing. Agent-run and function-invocation middleware
  (`Middleware/AgentMiddleware.cs`) cover the same "observe/intercept every turn or tool call" need
  in .NET today.
- **CodeAct** - the `MontyCodeActProvider` pattern shown in the Python samples
  (`python/samples/04-hosting/foundry-hosted-agents/responses/monty_codeact`) depends on an
  unpublished Hyperlight-based sandbox package with no .NET equivalent shipped yet.
- **Background Responses** - the OpenAI Responses API supports a `background: true` request field,
  but the hosting surface mapped here (`OpenAIResponseRequestInfo`, in
  `Microsoft.Agents.AI.Hosting.OpenAI`) does not currently expose that field for a
  `RunOptionsFactory` to forward, unlike `response_format` on the Chat Completions surface (which
  this sample does forward, see Structured Outputs above). A caller cannot request a background
  response through `/reference-agent/v1/responses` today. Setting
  `AgentRunOptions.AllowBackgroundResponses` is only possible from in-process code calling
  `agent.RunAsync(...)` directly, which defeats the "verify over the wire" goal of this sample, so
  it is not wired up here.
- A companion client project. Each hosting surface below links to the framework's own official
  sample client instead, so this sample stays focused on the server side.

## Hosting surfaces

| Surface | Route | Package | Notes |
| --- | --- | --- | --- |
| OpenAI Responses | `POST /reference-agent/v1/responses` (+ get/cancel/delete/list-input-items) | `Microsoft.Agents.AI.Hosting.OpenAI` | Stateful; conversation state is service-managed. |
| OpenAI Chat Completions | `POST /reference-agent/v1/chat/completions` | `Microsoft.Agents.AI.Hosting.OpenAI` | Stateless; caller resends the transcript every call. Honors client `response_format` (Structured Outputs). |
| OpenAI Responses (planner) | `POST /reference-agent-planner/v1/responses` | same | Identical agent, wrapped in a `LoopAgent` - compare against the route above to see the looping/planning difference. |
| OpenAI Chat Completions (planner) | `POST /reference-agent-planner/v1/chat/completions` | same | |
| OpenAI Conversations | `/v1/conversations` | `Microsoft.Agents.AI.Hosting.OpenAI` | Shared across every agent hosted in this process. |
| `GET /v1/models` | `/v1/models` | hand-rolled (see `Endpoints/ModelsEndpoint.cs`) | Not shipped by the framework as of this writing; a minimal, clearly-marked, app-owned route. |
| AG-UI | `/ag-ui` (SSE) | `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` | Streams over Server-Sent Events; natively surfaces the approval interrupt for `send_weather_alert`. |
| A2A | `/a2a` (HTTP+JSON and JSON-RPC), agent card at `/.well-known/agent-card.json` | `Microsoft.Agents.AI.Hosting.A2A(.AspNetCore)`, `A2A(.AspNetCore)` | Both wire shapes are mapped to the same agent. |
| DevUI | `/devui` | `Microsoft.Agents.AI.DevUI` | Visual, interactive test surface. Requires Responses + Conversations to be mapped, which they are above. |

## Why one agent instead of one demo per capability

Every capability above is reachable from the **same** `reference-agent` (or its looping sibling,
`reference-agent-planner`) conversation - triggered by what you ask, not by which URL you hit. Ask
about the weather and it calls `get_weather`; ask it to convert 10 miles to km and it uses the
unit-converter skill; ask about the refund policy and the RAG provider injects the FAQ answer; ask
it to write and run Python and it uses the hosted Code Interpreter. This mirrors how a real agent
is used, and keeps the "is this response real" question answerable in one place: whatever comes
back from `/reference-agent/v1/responses` or `/reference-agent/v1/chat/completions` is the literal,
unmodified JSON produced by `Microsoft.Agents.AI.Hosting.OpenAI`'s implementation of those two wire
formats - verify it with the official OpenAI SDK against this sample's own routes (see below), not
by trusting hand-written example payloads.

## Verifying a response is authentic

Point the **official OpenAI .NET or Python SDK** at this sample instead of a raw HTTP client, so
deserialization enforces the real schema instead of only "looks like JSON":

```csharp
// OpenAI .NET SDK, against the Chat Completions route:
ChatClient client = new(model: "reference-agent", credential: new ApiKeyCredential("unused"))
{
    // Point the SDK's transport at this sample instead of api.openai.com.
};
```

```python
# OpenAI Python SDK, against the Responses route:
from openai import OpenAI
client = OpenAI(base_url="http://localhost:5000/reference-agent/v1", api_key="unused")
response = client.responses.create(model="reference-agent", input="What's the weather in Lyon?")
print(response.output_text)  # `response` is a real openai.types.responses.Response instance.
```

If the SDK's own response model (`openai.types.responses.Response`,
`OpenAI.Responses.OpenAIResponse`) parses the payload without a validation error, and its typed
`output`/`choices` accessors return the expected content, the response is a real, spec-conformant
instance of that wire format - not a hand-rolled approximation. The same applies to the A2A route
with `A2A.A2AClient`/`A2ACardResolver`, and to AG-UI with any AG-UI-protocol client.

## Running

```bash
export OPENAI_API_KEY=sk-...
# optional: export OPENAI_CHAT_MODEL=gpt-4o-mini
# optional: export MCP_DOCS_ENDPOINT=https://learn.microsoft.com/api/mcp
dotnet run
```

Then, for example:

```bash
curl http://localhost:5000/v1/models

curl http://localhost:5000/reference-agent/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"reference-agent","messages":[{"role":"user","content":"What is the weather in Lyon?"}]}'

# Structured Outputs (forwarded response_format):
curl http://localhost:5000/reference-agent/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"reference-agent","messages":[{"role":"user","content":"Convert 10 miles to km"}],"response_format":{"type":"json_schema","json_schema":{"name":"conversion","schema":{"type":"object","properties":{"result":{"type":"number"}},"required":["result"]}}}}'

# Agent Looping / Planning: same question, planner route.
curl http://localhost:5000/reference-agent-planner/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"reference-agent-planner","messages":[{"role":"user","content":"Plan and then send a weather alert for Lyon if it is raining."}]}'
```

Or open `http://localhost:5000/devui` for an interactive test surface, or `/.well-known/agent-card.json`
to see what an A2A client discovers.

## Calling this agent from a client

Each hosting surface has an official Microsoft sample client; this sample deliberately does not
duplicate them:

- OpenAI Responses / Chat Completions: `dotnet/samples/05-end-to-end/AgentWebChat` in
  [microsoft/agent-framework](https://github.com/microsoft/agent-framework) (`OpenAIResponsesAgentClient.cs`,
  `OpenAIChatCompletionsAgentClient.cs`).
- AG-UI: `dotnet/samples/02-agents/AGUI/Step01_GettingStarted/Client`.
- A2A: `dotnet/samples/05-end-to-end/A2AClientServer/A2AClient`.

## Security notes (read before deploying anywhere but a laptop)

- **No authentication is configured.** Every route mapped above is open to anyone who can reach the
  process.
- **No `AgentIsolationKeyProvider` is registered.** Response ids, conversation ids, and A2A context
  ids are therefore shared lookup keys: anyone who learns one can read the state behind it. Register
  one (for example `services.UseClaimsBasedAgentIsolation(new() { ClaimType = ClaimTypes.NameIdentifier })`)
  before authenticating callers in a real deployment.
- The Microsoft Learn MCP endpoint (`https://learn.microsoft.com/api/mcp`) needs no credential and
  returns only public documentation content, so no secret is introduced by adding it as a tool.
- `send_weather_alert` is the only tool gated behind approval in this sample. Treat approval gating
  as a per-tool decision driven by what the tool actually does (a read vs. a notification, a
  purchase, a deletion), not as a blanket setting.
- The hosted MCP tool is configured with `HostedMcpServerToolApprovalMode.AlwaysRequire`: every call
  to the Microsoft Learn MCP server also requires human approval in this sample, purely to
  demonstrate approval against a provider-hosted (not locally-executed) tool - the Learn server
  itself carries no confidentiality risk.

## Known gaps / unverified areas

This project could not be compiled in the sandbox this sample was authored in
(`dotnet restore` failed with `NU1301: 403 Forbidden` reaching `api.nuget.org` - an environment
restriction, not a code issue). Every API used here was verified against the actual
`microsoft/agent-framework` and `openai-dotnet` source on GitHub, but nothing has been compiled.
Before relying on this sample, run `dotnet build` yourself and treat these as the most likely spots
to need adjustment for the exact package versions you resolve:

- `OpenAIFileClient`/`VectorStoreClient` member names and the `CreateVectorStoreOperation` /
  `waitUntilCompleted` shape used in `CreateSampleKnowledgeBaseAsync` (`Program.cs`) - the OpenAI
  .NET SDK's vector-store API has changed shape across 2.x releases.
- The `AgentCard`/`AgentSkill`/`AgentCapabilities` construction - the `A2A` NuGet package is still
  under active development.
- `AgentInlineSkill.AddResource`/`.AddScript` fluent method names and `AgentSkillsProvider`
  constructor signature (confirmed to exist in `Microsoft.Agents.AI`; exact overload shapes not
  independently confirmed against a compiled build).

## Relationship to `ai-enterprise-agent-runtime`

This sample is intentionally "bare framework": every capability above comes from
`Microsoft.Agents.AI*` packages alone. When evaluating what the runtime library in this repository
should add on top (authentication normalization, standard exchange contracts, human-approval
policy, audit, session leasing, etc.), compare against this baseline rather than against the
harness agent or a workflow, since those solve different problems.

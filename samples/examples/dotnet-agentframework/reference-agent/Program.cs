// Copyright (c) Microsoft. All rights reserved.

// Reference sample: every capability of a *standard* Microsoft Agent Framework .NET agent
// (Microsoft.Agents.AI.ChatClientAgent), exposed through the hosting surfaces Microsoft documents:
// OpenAI Responses, OpenAI Chat Completions, OpenAI Conversations, A2A, and AG-UI.
//
// Deliberately excluded, and out of scope for this sample (see README.md "Scope"):
//   - Microsoft.Agents.AI.Harness: a different, opinionated agent type with its own planning,
//     compaction, and memory. This sample uses the standard ChatClientAgent throughout.
//   - Microsoft.Agents.AI.Workflows: multi-agent, graph-based orchestration. This sample is
//     single-agent.
//
// This sample has NO dependency on ai-enterprise-agent-runtime. It is the framework-only baseline
// that an integration against that library is written, and measured, against.

using System.ClientModel;
using A2A;
using A2A.AspNetCore;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Hosting.AGUI.AspNetCore;
using Microsoft.Agents.AI.Hosting.OpenAI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Logging;
using OpenAI;
using OpenAI.Files;
using OpenAI.Responses;
using OpenAI.VectorStores;
using OpenTelemetry;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using ReferenceAgent.Endpoints;
using ReferenceAgent.Middleware;
using ReferenceAgent.Rag;
using ReferenceAgent.Tools;

#pragma warning disable OPENAI001 // ResponsesClient, OpenAIFileClient, VectorStoreClient are evaluation-stage in the OpenAI SDK.

const string AgentName = "reference-agent";
const string PlannerAgentName = "reference-agent-planner";
const string TelemetrySourceName = "ReferenceAgent";
const string AgentDescription =
    "Reference Microsoft Agent Framework agent: one ChatClientAgent whose capabilities (function " +
    "tools, hosted Code Interpreter/File Search/MCP tools, an approval-gated tool, an Agent Skill, " +
    "a RAG context provider, planning/todos, and OpenTelemetry instrumentation) are all reachable " +
    "from the same conversation - hosted over OpenAI Responses, OpenAI Chat Completions, OpenAI " +
    "Conversations, A2A, and AG-UI. A second route (reference-agent-planner) wraps the identical " +
    "agent in a LoopAgent to demonstrate multi-step looping/planning.";

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

builder.Logging.AddSimpleConsole(options => options.SingleLine = true);

// ── Hosting services ─────────────────────────────────────────────────────────
// Registering a service wires the protocol <-> agent conversion; mapping the matching endpoint
// (further down) is what actually exposes it on a route. Each surface is independently optional.
builder.Services.AddOpenAIResponses();
builder.Services.AddOpenAIChatCompletions();
builder.Services.AddOpenAIConversations();
builder.Services.AddAGUIServer();

// WARNING: this sample registers no authentication and no AgentIsolationKeyProvider. Every
// response id / conversation id / A2A context id is therefore a shared lookup key: anyone who
// learns one can read the state behind it. A production deployment must authenticate callers and
// call, for example, `builder.Services.UseClaimsBasedAgentIsolation(new() { ClaimType = ... })`
// before relying on any of the session/conversation persistence enabled below.

// ── Observability ─────────────────────────────────────────────────────────────
// Capability demo: Observability. Traces every chat-client call and agent run to the console via
// OpenTelemetry - no Azure Monitor / Application Insights dependency. Point an OTLP collector (for
// example the local Aspire Dashboard, `docker run -p 18888:18888 -p 4317:18889
// mcr.microsoft.com/dotnet/aspire-dashboard`) at this process by uncommenting AddOtlpExporter below.
using TracerProvider tracerProvider = Sdk.CreateTracerProviderBuilder()
    .SetResourceBuilder(ResourceBuilder.CreateDefault().AddService(AgentName))
    .AddSource(TelemetrySourceName)
    .AddConsoleExporter()
    // .AddOtlpExporter(o => o.Endpoint = new Uri("http://localhost:4317"))
    .Build();

// ── Model client ──────────────────────────────────────────────────────────────
string apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY")
    ?? throw new InvalidOperationException("OPENAI_API_KEY is not set.");
string model = Environment.GetEnvironmentVariable("OPENAI_CHAT_MODEL") ?? "gpt-4o-mini";

// The Responses API is used as the single underlying client for the whole sample: it is a superset
// of Chat Completions capability-wise (it also backs the /v1/chat/completions surface below via
// AsIChatClient), and it is the only API that supports Background Responses and the hosted
// Code Interpreter / File Search / MCP tools used further down.
OpenAIClient openAIClient = new(new ApiKeyCredential(apiKey));
ResponsesClient responsesClient = openAIClient.GetResponsesClient();

// ── Tools ─────────────────────────────────────────────────────────────────────
using ILoggerFactory startupLoggerFactory = LoggerFactory.Create(logging => logging.AddSimpleConsole(o => o.SingleLine = true));
ILogger startupLogger = startupLoggerFactory.CreateLogger("ReferenceAgent.Startup");

// A plain function tool: the model may call it without asking anyone first.
AIFunction weatherTool = AIFunctionFactory.Create(WeatherTools.GetWeather, name: "get_weather");

// A function tool gated behind human approval. Every hosting surface below carries the resulting
// ToolApprovalRequestContent / ToolApprovalResponseContent pair through its own wire shape (Responses
// items, ChatCompletions tool-call content, A2A message parts, or the AG-UI approval interrupt), so
// nothing else in this file has to special-case it.
AITool approvalGatedTool = new ApprovalRequiredAIFunction(
    AIFunctionFactory.Create(WeatherTools.SendWeatherAlert, name: "send_weather_alert"));

// Capability demo: Hosted MCP Tool. Unlike a client-opened MCP connection (McpClient/McpClientTool),
// this tool is executed by the model provider itself - OpenAI's Responses API calls the remote MCP
// server directly, and only the tool call/result pass through this process. This is the pattern
// documented at https://platform.openai.com/docs/guides/tools-remote-mcp, and it works against any
// plain (non-Foundry) OpenAI account - the account only needs the model access already required for
// this sample. Approval is required for every call, exercising Tool Approval against a second,
// provider-hosted tool (distinct from the local send_weather_alert tool above).
string docsEndpoint = Environment.GetEnvironmentVariable("MCP_DOCS_ENDPOINT") ?? "https://learn.microsoft.com/api/mcp";
var hostedDocsTool = new HostedMcpServerTool(serverName: "microsoft_learn", serverAddress: docsEndpoint)
{
    AllowedTools = ["microsoft_docs_search", "microsoft_docs_fetch", "microsoft_code_sample_search"],
    ApprovalMode = HostedMcpServerToolApprovalMode.AlwaysRequire,
};

// Capability demo: Code Interpreter. Provider-hosted Python sandbox; OpenAI-direct, no Foundry
// project required.
var codeInterpreterTool = new HostedCodeInterpreterTool();

// Capability demo: File Search (a second, hosted-tool flavor of retrieval, alongside the RAG
// context provider below). Creates a tiny vector store at startup so the tool has something to
// find. NOTE: file/vector-store client member names are the least-verified part of this sample
// (no network access to compile-check here) - adjust against the installed `OpenAI` package
// version if this does not compile.
async Task<string> CreateSampleKnowledgeBaseAsync()
{
    OpenAIFileClient fileClient = openAIClient.GetOpenAIFileClient();
    VectorStoreClient vectorStoreClient = openAIClient.GetVectorStoreClient();

    OpenAIFile file = await fileClient.UploadFileAsync(
        BinaryData.FromString(
            "Reference Agent product manual: the DevKit 3000 ships with a 90-day limited hardware " +
            "warranty and requires firmware 2.1 or later for Bluetooth pairing."),
        "devkit-3000-manual.txt",
        FileUploadPurpose.UserData).ConfigureAwait(false);

    CreateVectorStoreOperation createOperation = await vectorStoreClient.CreateVectorStoreAsync(
        waitUntilCompleted: true,
        new VectorStoreCreationOptions { Name = "reference-agent-file-search-kb" }).ConfigureAwait(false);
    await vectorStoreClient.AddFileToVectorStoreAsync(
        createOperation.VectorStoreId,
        file.Id,
        waitUntilCompleted: true).ConfigureAwait(false);

    return createOperation.VectorStoreId;
}

string knowledgeBaseVectorStoreId = await CreateSampleKnowledgeBaseAsync().ConfigureAwait(false);
var fileSearchTool = new HostedFileSearchTool { Inputs = [new HostedVectorStoreContent(knowledgeBaseVectorStoreId)] };

List<AITool> tools = [weatherTool, approvalGatedTool, hostedDocsTool, codeInterpreterTool, fileSearchTool];

// Capability demo: Agent Skills. A reusable, self-contained capability the model can discover and
// invoke as a unit (instructions + a data resource + a runnable script), distinct from a plain
// function tool.
AgentInlineSkill unitConverterSkill = new AgentInlineSkill(
        name: "unit-converter",
        description: "Converts between common units (distance, weight) using a fixed conversion factor.",
        instructions: """
            Use this skill whenever the user asks to convert between units.
            1. Read the conversion-table resource to find the correct factor for the requested units.
            2. Call the convert script with the value and that factor.
            3. Report the result together with both units.
            """)
    .AddResource("conversion-table", """
        # Conversion Tables
        Formula: result = value * factor
        | From       | To         | Factor   |
        |------------|------------|----------|
        | miles      | kilometers | 1.60934  |
        | kilometers | miles      | 0.621371 |
        | pounds     | kilograms  | 0.453592 |
        | kilograms  | pounds     | 2.20462  |
        """)
    .AddScript("convert", (double value, double factor) => Math.Round(value * factor, 4));

var skillsProvider = new AgentSkillsProvider(unitConverterSkill);

// Capability demo: RAG. A context provider that runs a retrieval step before every model call and
// injects matching snippets into context - the same mechanism a production RAG integration uses
// (see Rag/FaqSearch.cs), just with a keyword-matched, in-memory "index" standing in for a real
// vector database.
var ragProvider = new TextSearchProvider(FaqSearch.SearchAsync, new TextSearchProviderOptions
{
    SearchTime = TextSearchProviderOptions.TextSearchBehavior.BeforeAIInvoke,
    RecentMessageMemoryLimit = 4,
});

// Capability demo: Planning and Todos. TodoProvider exposes a scratchpad the model can use to track
// a multi-step plan; AgentModeProvider lets the same agent switch between a "plan" mode (think,
// break the task down) and an "execute" mode (act on the plan) across turns. Both are ordinary
// context providers on this same agent - the reference-agent-planner route (below) additionally
// wraps the agent in a LoopAgent that keeps running turns until the plan is marked complete.
var todoProvider = new TodoProvider();
var modeProvider = new AgentModeProvider(new AgentModeProviderOptions { DefaultMode = "plan" });

// ── Agent ─────────────────────────────────────────────────────────────────────
// The standard agent type (ChatClientAgent, returned by AsAIAgent), not Microsoft.Agents.AI.Harness:
// this sample shows the primitives an integration is built on, not a batteries-included harness.
//
// Chat-level middleware (Middleware/ChatMiddleware.cs) is applied to the IChatClient before the
// agent is built, so it sees one call per model round-trip. Agent-run and function-invocation
// middleware (Middleware/AgentMiddleware.cs) and OpenTelemetry are applied via AsBuilder() below,
// after the agent is built, so they see one call per user turn / per tool call.
//
// Capability demo: Multimodal is not a separate code path - it falls out of ChatClientAgent already
// accepting DataContent/UriContent (images, audio, PDFs) in any incoming ChatMessage. Send an image
// to any endpoint below with the official OpenAI SDK's image-content message shape to exercise it.
IChatClient instrumentedChatClient = responsesClient
    .AsIChatClient(model)
    .AsBuilder()
    .Use(ChatMiddleware.LoggingMiddleware(startupLogger))
    .Build();

ChatClientAgent baseAgent = instrumentedChatClient.AsAIAgent(new ChatClientAgentOptions
{
    Name = AgentName,
    Description = AgentDescription,
    ChatOptions = new ChatOptions
    {
        Instructions = """
            You are a helpful assistant with access to weather tools, a hosted Microsoft Learn
            documentation MCP tool, a code interpreter, a file search tool, and a unit-converter
            skill. Prefer the documentation tool over your own memory for any question about a
            Microsoft technology, API, or SDK: your training data can be stale or wrong about
            fast-moving surfaces, and the tool is not.
            """,
        Tools = tools,
    },
    AIContextProviders = [skillsProvider, ragProvider, todoProvider, modeProvider],
});

AIAgent agent = baseAgent
    .AsBuilder()
    .UseOpenTelemetry(sourceName: TelemetrySourceName, configure: cfg => cfg.EnableSensitiveData = true)
    .Use(AgentMiddleware.LoggingMiddleware(startupLogger))
    .Use(AgentMiddleware.LogFunctionCallsAsync)
    .Build();

builder.Services.AddKeyedSingleton(AgentName, agent);

// Capability demo: Agent Looping. Wraps the identical, fully-configured agent above in a LoopAgent
// that keeps invoking it until the todo list this same agent maintains (via TodoProvider above) is
// marked complete, or MaxIterations is hit. Exposed under its own route further down so both the
// single-turn and the looping behavior of the same agent can be compared side by side.
AIAgent plannerAgent = new LoopAgent(
    agent,
    new TodoCompletionLoopEvaluator(new TodoCompletionLoopEvaluatorOptions { Modes = ["execute"] }),
    new LoopAgentOptions { MaxIterations = 10 });

builder.Services.AddKeyedSingleton(PlannerAgentName, plannerAgent);

// Capability demo: Structured Outputs. The default OpenAIChatCompletionsMapOptions rejects any
// client-supplied `response_format`, to keep this self-contained agent from being reconfigured by a
// caller (see Microsoft.Agents.AI.Hosting.OpenAI.OpenAIChatCompletionsMapOptions.RejectRequestSettings).
// This sample opts in to honoring that one field - and only that field - so a caller using the
// official OpenAI SDK's `response_format` / Pydantic `response_format` on
// /reference-agent/v1/chat/completions gets back real, schema-conformant JSON.
// NOTE: the OpenAI Responses hosting surface (OpenAIResponseRequestInfo) does not currently expose a
// `background` field to map at all, so Background Responses cannot be exercised as a caller-set
// option on the Responses route above; see README.md "Known gaps" for the source citation and the
// workaround (setting AgentRunOptions.AllowBackgroundResponses in-process instead).
var chatCompletionsMapOptions = new OpenAIChatCompletionsMapOptions
{
    RunOptionsFactory = request => request.ResponseFormat is null
        ? null
        : new ChatClientAgentRunOptions(new ChatOptions { ResponseFormat = request.ResponseFormat }),
};

// ── A2A ───────────────────────────────────────────────────────────────────────
// Registers the A2A server wrapping the keyed agent above; MapA2AHttpJson/MapA2AJsonRpc (below) are
// what actually put it on the wire.
builder.Services.AddA2AServer(AgentName);

WebApplication app = builder.Build();

// ── OpenAI-compatible surfaces ────────────────────────────────────────────────
// POST /reference-agent/v1/responses (+ get/cancel/delete/list-input-items)
app.MapOpenAIResponses(agent);
// POST /reference-agent/v1/chat/completions
app.MapOpenAIChatCompletions(agent, path: null, mapOptions: chatCompletionsMapOptions);
// /v1/conversations - shared across every agent hosted in this process.
app.MapOpenAIConversations();
// Non-standard extension this sample owns itself: see Endpoints/ModelsEndpoint.cs.
app.MapAgentAsModel(AgentName, AgentDescription);

// Capability demo: Agent Looping / Planning and Todos, continued from above. Same agent, same
// tools/skills/RAG, but wrapped in a LoopAgent and addressed under its own name/route so a caller
// can compare `reference-agent` (single turn) against `reference-agent-planner` (loops turns until
// its own todo list is complete) using the identical OpenAI Responses/ChatCompletions wire format.
// NOTE: plannerAgent.Name is inherited from the wrapped `agent` (LoopAgent is a DelegatingAIAgent
// with no Name override), so both routes below are mapped under explicit, distinct paths rather
// than relying on the `/{agent.Name}/...` default, to avoid colliding with the routes above.
app.MapOpenAIResponses(plannerAgent, responsesPath: $"/{PlannerAgentName}/v1/responses");
app.MapOpenAIChatCompletions(plannerAgent, path: $"/{PlannerAgentName}/v1/chat/completions", mapOptions: chatCompletionsMapOptions);

// ── AG-UI ─────────────────────────────────────────────────────────────────────
// Streams over Server-Sent Events; natively emits the approval interrupt for the tool gated above,
// and resumes the run when the client sends the decision back - no extra wiring needed here.
app.MapAGUIServer("/ag-ui", agent);

// ── A2A over HTTP ─────────────────────────────────────────────────────────────
app.MapA2AHttpJson(AgentName, "/a2a");
app.MapA2AJsonRpc(AgentName, "/a2a");

// Publishes the agent card at the well-known discovery path A2A clients probe first.
// NOTE: adjust member names to the installed A2A package version if it has moved since this sample
// was written; the AgentCard shape is still stabilizing under active development.
AgentCard agentCard = new()
{
    Name = AgentName,
    Description = AgentDescription,
    Url = "/a2a",
    Version = "1.0.0",
    DefaultInputModes = ["text/plain"],
    DefaultOutputModes = ["text/plain"],
    Capabilities = new AgentCapabilities { Streaming = true },
    Skills =
    [
        new AgentSkill
        {
            Id = "weather",
            Name = "Weather lookup and alerts",
            Description = "Reports current weather, and can send a weather alert once a human approves it.",
            Tags = ["weather"],
        },
        new AgentSkill
        {
            Id = "microsoft-docs",
            Name = "Microsoft documentation search",
            Description = "Searches, fetches, and finds code samples in Microsoft's official documentation.",
            Tags = ["docs", "mcp"],
        },
        new AgentSkill
        {
            Id = "unit-converter",
            Name = "Unit conversion",
            Description = "Converts between common distance and weight units.",
            Tags = ["skill", "conversion"],
        },
    ],
};
app.MapWellKnownAgentCard(agentCard);

// ── DevUI ─────────────────────────────────────────────────────────────────────
// Visual, interactive test surface at /devui. Requires the OpenAI Responses and Conversations
// services and endpoints mapped above.
app.MapDevUI();

await app.RunAsync().ConfigureAwait(false);

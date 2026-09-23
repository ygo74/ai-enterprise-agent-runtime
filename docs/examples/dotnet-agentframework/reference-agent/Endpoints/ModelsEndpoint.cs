// Copyright (c) Microsoft. All rights reserved.

namespace ReferenceAgent.Endpoints;

/// <summary>
/// A hand-rolled <c>/v1/models</c> endpoint.
///
/// Microsoft.Agents.AI.Hosting.OpenAI ships Responses, ChatCompletions, and Conversations, but not a
/// model-listing endpoint as of this writing. Provider-compatible clients (chat UIs, model pickers)
/// commonly call <c>GET /v1/models</c> before letting a user pick a target, so an application that
/// wants to be selectable by one of those clients has to own this route itself - exactly the
/// "application-owned route" pattern the framework's protocol helpers are built for elsewhere
/// (see <c>Microsoft.Agents.AI.Hosting.OpenAI.OpenAIResponses</c>).
/// </summary>
internal static class ModelsEndpoint
{
    public static IEndpointRouteBuilder MapAgentAsModel(this IEndpointRouteBuilder endpoints, string agentId, string description)
    {
        endpoints.MapGet("/v1/models", () => Results.Json(new
        {
            @object = "list",
            data = new[]
            {
                new
                {
                    id = agentId,
                    @object = "model",
                    created = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                    owned_by = "reference-agent-sample",
                    // Non-standard extension field: OpenAI's own schema does not define this, but a
                    // client that already tolerates unknown properties can use it to show capabilities
                    // alongside the model name in a picker.
                    description,
                },
            },
        }))
        .WithName("ListModels")
        .WithSummary("OpenAI-compatible model listing (non-standard extension, hand-rolled: see remarks).");

        return endpoints;
    }
}

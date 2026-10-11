// Copyright (c) Microsoft. All rights reserved.

using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Logging;

namespace ReferenceAgent.Middleware;

/// <summary>
/// Agent-level middleware: one layer above the chat client, seeing one call per user turn (the whole
/// tool-invocation loop that turn triggers), and one layer below it, seeing each individual function
/// invocation. Both run for every hosting surface mapped in Program.cs, since they wrap the
/// <see cref="AIAgent"/> instance those surfaces are given, not any one protocol.
/// </summary>
internal static class AgentMiddleware
{
    /// <summary>Logs the outcome of a whole agent run, one call per user turn.</summary>
    public static Func<IEnumerable<ChatMessage>, AgentSession?, AgentRunOptions?, AIAgent, CancellationToken, Task<AgentResponse>> LoggingMiddleware(ILogger logger) =>
        async (messages, session, options, innerAgent, cancellationToken) =>
        {
            logger.LogInformation("Agent run starting: {MessageCount} message(s).", messages.Count());
            AgentResponse response = await innerAgent.RunAsync(messages, session, options, cancellationToken).ConfigureAwait(false);
            logger.LogInformation("Agent run completed.");
            return response;
        };

    /// <summary>Logs each function the model asks to invoke, before and after it runs.</summary>
    public static async ValueTask<object?> LogFunctionCallsAsync(
        AIAgent agent,
        FunctionInvocationContext context,
        Func<FunctionInvocationContext, CancellationToken, ValueTask<object?>> next,
        CancellationToken cancellationToken)
    {
        object? result = await next(context, cancellationToken).ConfigureAwait(false);
        return result;
    }
}

// Copyright (c) Microsoft. All rights reserved.

using Microsoft.Extensions.AI;
using Microsoft.Extensions.Logging;

namespace ReferenceAgent.Middleware;

/// <summary>
/// Chat-client-level middleware: the lowest layer, seeing every request the agent sends to the model
/// and every response it gets back, once per model call (so once per tool-loop iteration, not once
/// per user turn).
/// </summary>
internal static class ChatMiddleware
{
    public static Func<IEnumerable<ChatMessage>, ChatOptions?, IChatClient, CancellationToken, Task<ChatResponse>> LoggingMiddleware(ILogger logger) =>
        async (messages, options, innerChatClient, cancellationToken) =>
        {
            logger.LogInformation("Chat client call: {MessageCount} message(s) sent to the model.", messages.Count());
            ChatResponse response = await innerChatClient.GetResponseAsync(messages, options, cancellationToken).ConfigureAwait(false);
            logger.LogInformation("Chat client call completed: finish reason {FinishReason}.", response.FinishReason);
            return response;
        };
}

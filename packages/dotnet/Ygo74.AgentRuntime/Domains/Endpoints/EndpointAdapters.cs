using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Domains.Endpoints;

public static class EndpointAdapters
{
    private static readonly HashSet<string> Supported =
    [
        "openai.chat_completions",
        "openai.responses",
        "anthropic.messages"
    ];

    public static StandardExchangeRequest Normalize(string endpointType, string requestId, string routeKey, object input, bool stream = false, IDictionary<string, object?>? metadata = null)
    {
        if (!Supported.Contains(endpointType))
        {
            throw new ArgumentException($"Unsupported endpoint type: {endpointType}", nameof(endpointType));
        }

        return new StandardExchangeRequest(requestId, routeKey, endpointType, input, stream, metadata);
    }
}

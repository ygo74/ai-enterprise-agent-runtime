namespace Ygo74.AgentRuntime.Domains.Configuration;

public sealed class EndpointOptions
{
    public required string RouteKey { get; init; }
    public bool EnableChatCompletions { get; init; }
    public bool EnableResponses { get; init; }
    public bool EnableAnthropicMessages { get; init; }
    public bool EnableStreaming { get; init; }
}

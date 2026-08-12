namespace Ygo74.AgentRuntime.Domains.Configuration;

public static class EndpointOptionsValidator
{
    public static void Validate(EndpointOptions options)
    {
        if (string.IsNullOrWhiteSpace(options.RouteKey))
        {
            throw new ArgumentException("RouteKey is required", nameof(options));
        }

        if (!options.EnableChatCompletions && !options.EnableResponses && !options.EnableAnthropicMessages)
        {
            throw new ArgumentException("At least one endpoint surface must be enabled", nameof(options));
        }
    }
}

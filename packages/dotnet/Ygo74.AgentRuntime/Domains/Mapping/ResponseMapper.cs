using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Domains.Mapping;

public static class ResponseMapper
{
    public static IDictionary<string, object?> ToEndpoint(StandardExchangeResponse response)
    {
        return new Dictionary<string, object?>
        {
            ["request_id"] = response.RequestId,
            ["status"] = response.Status,
            ["output"] = response.Output,
            ["error"] = response.Error
        };
    }
}

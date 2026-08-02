using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime;

public static class PublicApi
{
    public static string NamespaceRoot => "Ygo74";

    public static StandardExchangeRequest CreateRequest(string requestId, string routeKey, string endpointType, object input)
        => new(requestId, routeKey, endpointType, input);
}

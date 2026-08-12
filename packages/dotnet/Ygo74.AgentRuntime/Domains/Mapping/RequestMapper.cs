using Ygo74.AgentRuntime.Domains.Contracts;
using Ygo74.AgentRuntime.Domains.Endpoints;

namespace Ygo74.AgentRuntime.Domains.Mapping;

public static class RequestMapper
{
    public static StandardExchangeRequest ToExchange(string endpointType, string requestId, string routeKey, object input, bool stream = false, IDictionary<string, object?>? metadata = null)
        => EndpointAdapters.Normalize(endpointType, requestId, routeKey, input, stream, metadata);
}

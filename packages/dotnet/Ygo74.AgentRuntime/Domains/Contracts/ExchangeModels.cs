namespace Ygo74.AgentRuntime.Domains.Contracts;

public sealed record StandardExchangeRequest(
    string RequestId,
    string RouteKey,
    string EndpointType,
    object Input,
    bool Stream = false,
    IDictionary<string, object?>? Metadata = null,
    IDictionary<string, object?>? AuthContext = null
);

public sealed record StandardExchangeResponse(
    string RequestId,
    string Status,
    object? Output = null,
    ErrorEnvelope? Error = null,
    IDictionary<string, object?>? Metadata = null
);

using Ygo74.AgentRuntime.Domains.Contracts;

namespace Examples.Handlers;

public sealed class BasicHandler
{
    public StandardExchangeResponse Handle(StandardExchangeRequest request)
        => new(request.RequestId, "success", new { message = "ok" });
}

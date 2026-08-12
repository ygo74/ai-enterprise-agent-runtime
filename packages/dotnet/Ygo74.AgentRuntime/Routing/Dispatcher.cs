using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Routing;

public sealed class Dispatcher : IDispatcher
{
    public StandardExchangeResponse Dispatch(StandardExchangeRequest request, Func<string, UseCaseHandler> resolver)
    {
        var handler = resolver(request.RouteKey);
        return handler(request);
    }
}

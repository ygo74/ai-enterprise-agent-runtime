using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Routing;

public delegate StandardExchangeResponse UseCaseHandler(StandardExchangeRequest request);

public interface IDispatcher
{
    StandardExchangeResponse Dispatch(StandardExchangeRequest request, Func<string, UseCaseHandler> resolver);
}

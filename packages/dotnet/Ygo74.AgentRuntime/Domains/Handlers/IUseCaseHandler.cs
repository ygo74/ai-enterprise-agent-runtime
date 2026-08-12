using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Domains.Handlers;

public interface IUseCaseHandler
{
    StandardExchangeResponse Handle(StandardExchangeRequest request);
}

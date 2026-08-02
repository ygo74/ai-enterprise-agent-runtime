using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Middleware;

public sealed class MessagePipelineContext
{
    public required StandardExchangeRequest Request { get; init; }
    public StandardExchangeResponse? Response { get; set; }
}

public interface IMiddleware
{
    StandardExchangeResponse Invoke(MessagePipelineContext context, Func<MessagePipelineContext, StandardExchangeResponse> next);
}

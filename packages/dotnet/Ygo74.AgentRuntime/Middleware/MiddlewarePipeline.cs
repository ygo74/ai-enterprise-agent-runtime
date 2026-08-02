using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Middleware;

public static class MiddlewarePipeline
{
    public static StandardExchangeResponse Execute(
        MessagePipelineContext context,
        IReadOnlyList<IMiddleware> middlewares,
        Func<MessagePipelineContext, StandardExchangeResponse> handler)
    {
        StandardExchangeResponse Next(int index, MessagePipelineContext ctx)
        {
            if (index >= middlewares.Count)
            {
                return handler(ctx);
            }

            return middlewares[index].Invoke(ctx, next => Next(index + 1, next));
        }

        return Next(0, context);
    }
}

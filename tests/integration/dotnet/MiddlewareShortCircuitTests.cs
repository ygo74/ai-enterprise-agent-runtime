using System;
using System.Collections.Generic;
using Xunit;
using Ygo74.AgentRuntime.Domains.Contracts;
using Ygo74.AgentRuntime.Middleware;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class MiddlewareShortCircuitTests
{
    private sealed class ShortCircuit : IMiddleware
    {
        public StandardExchangeResponse Invoke(MessagePipelineContext context, Func<MessagePipelineContext, StandardExchangeResponse> next)
            => new(context.Request.RequestId, "success", "short");
    }

    [Fact]
    public void Middleware_Can_ShortCircuit()
    {
        var ctx = new MessagePipelineContext { Request = new StandardExchangeRequest("r1", "demo", "openai.responses", "hi") };
        var outp = MiddlewarePipeline.Execute(ctx, new List<IMiddleware> { new ShortCircuit() }, c => new StandardExchangeResponse(c.Request.RequestId, "success", "handler"));
        Assert.Equal("short", outp.Output?.ToString());
    }
}

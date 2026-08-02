using System;
using System.Collections.Generic;
using Xunit;
using Ygo74.AgentRuntime.Domains.Contracts;
using Ygo74.AgentRuntime.Middleware;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class MiddlewarePipelineTests
{
    private sealed class PassThrough : IMiddleware
    {
        public StandardExchangeResponse Invoke(MessagePipelineContext context, Func<MessagePipelineContext, StandardExchangeResponse> next)
            => next(context);
    }

    [Fact]
    public void MiddlewarePipeline_Executes_Handler()
    {
        var ctx = new MessagePipelineContext { Request = new StandardExchangeRequest("r1", "demo", "openai.responses", "hi") };
        var outp = MiddlewarePipeline.Execute(ctx, new List<IMiddleware> { new PassThrough() }, c => new StandardExchangeResponse(c.Request.RequestId, "success", "ok"));
        Assert.Equal("success", outp.Status);
    }
}

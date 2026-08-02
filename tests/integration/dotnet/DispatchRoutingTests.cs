using Xunit;
using Ygo74.AgentRuntime.Domains.Contracts;
using Ygo74.AgentRuntime.Routing;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class DispatchRoutingTests
{
    [Fact]
    public void Dispatcher_Resolves_Registered_Handler()
    {
        var registry = new RouteRegistry();
        registry.Register("demo", req => new StandardExchangeResponse(req.RequestId, "success", "ok"));
        var dispatcher = new Dispatcher();
        var outp = dispatcher.Dispatch(new StandardExchangeRequest("r1", "demo", "openai.responses", "hi"), registry.Resolve);
        Assert.Equal("success", outp.Status);
    }
}

using Xunit;
using Ygo74.AgentRuntime.Domains.Endpoints;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class NonStreamEndpointsTests
{
    [Fact]
    public void Normalize_OpenAi_And_Anthropic_Endpoints()
    {
        var chat = EndpointAdapters.Normalize("openai.chat_completions", "r1", "demo", "hello");
        var resp = EndpointAdapters.Normalize("openai.responses", "r1", "demo", "hello");
        var anth = EndpointAdapters.Normalize("anthropic.messages", "r1", "demo", "hello");

        Assert.Equal("r1", chat.RequestId);
        Assert.Equal("openai.responses", resp.EndpointType);
        Assert.Equal("anthropic.messages", anth.EndpointType);
    }
}

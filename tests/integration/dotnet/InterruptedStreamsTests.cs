using Xunit;
using Ygo74.AgentRuntime.Domains.Contracts;
using Ygo74.AgentRuntime.Domains.Streaming;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class InterruptedStreamsTests
{
    [Fact]
    public void Interrupted_Stream_Maps_To_Error_Event()
    {
        var err = new ErrorEnvelope("stream_interrupted", "mapping", "interrupted");
        var evt = StreamTermination.Error("r1", 2, err);
        Assert.Equal("error", evt.EventType);
        Assert.NotNull(evt.Error);
    }
}

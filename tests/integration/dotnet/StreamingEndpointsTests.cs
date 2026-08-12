using Xunit;
using Ygo74.AgentRuntime.Domains.Streaming;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class StreamingEndpointsTests
{
    [Fact]
    public void OpenAi_Stream_Chunk_Is_Mapped()
    {
        var evt = OpenAiStreamMapper.MapChunk("r1", 1, new { delta = "a" });
        Assert.Equal("chunk", evt.EventType);
        Assert.Equal(1, evt.Sequence);
    }
}

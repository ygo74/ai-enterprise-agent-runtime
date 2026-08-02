using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Domains.Streaming;

public static class OpenAiStreamMapper
{
    public static StreamingEvent MapChunk(string requestId, int sequence, object delta)
        => new(requestId, sequence, "chunk", delta);
}

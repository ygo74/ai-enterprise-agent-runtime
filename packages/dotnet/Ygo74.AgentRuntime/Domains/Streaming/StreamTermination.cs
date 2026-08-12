using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Domains.Streaming;

public static class StreamTermination
{
    public static StreamingEvent Completion(string requestId, int sequence, object finalOutput)
        => new(requestId, sequence, "completion", null, finalOutput);

    public static StreamingEvent Error(string requestId, int sequence, ErrorEnvelope error)
        => new(requestId, sequence, "error", null, null, error);
}

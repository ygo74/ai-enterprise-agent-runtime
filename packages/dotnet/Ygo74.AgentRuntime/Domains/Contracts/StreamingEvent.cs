namespace Ygo74.AgentRuntime.Domains.Contracts;

public sealed record StreamingEvent(
    string RequestId,
    int Sequence,
    string EventType,
    object? Delta = null,
    object? FinalOutput = null,
    ErrorEnvelope? Error = null
);

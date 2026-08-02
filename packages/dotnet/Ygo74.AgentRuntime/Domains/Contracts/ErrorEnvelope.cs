namespace Ygo74.AgentRuntime.Domains.Contracts;

public sealed record ErrorEnvelope(
    string Code,
    string Category,
    string Message,
    object? Details = null,
    string? RequestId = null,
    bool? Retryable = null
);

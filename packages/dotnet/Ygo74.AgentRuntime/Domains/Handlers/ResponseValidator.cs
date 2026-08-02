using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Domains.Handlers;

public static class ResponseValidator
{
    public static void Validate(StandardExchangeResponse response)
    {
        if (response.Status is not ("success" or "error"))
        {
            throw new ArgumentException("status must be success or error", nameof(response));
        }

        if (response.Status == "success" && response.Output is null)
        {
            throw new ArgumentException("success response must include output", nameof(response));
        }

        if (response.Status == "error" && response.Error is null)
        {
            throw new ArgumentException("error response must include error", nameof(response));
        }
    }
}

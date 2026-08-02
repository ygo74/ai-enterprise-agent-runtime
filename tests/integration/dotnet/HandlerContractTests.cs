using Xunit;
using Ygo74.AgentRuntime.Domains.Contracts;
using Ygo74.AgentRuntime.Domains.Handlers;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class HandlerContractTests
{
    [Fact]
    public void ResponseValidator_Accepts_Valid_Success_Response()
    {
        var response = new StandardExchangeResponse("r1", "success", new { ok = true });
        ResponseValidator.Validate(response);
    }
}

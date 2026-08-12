using Xunit;
using Ygo74.AgentRuntime.Domains.Configuration;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class OptionsBindingTests
{
    [Fact]
    public void Valid_Options_Pass_Validation()
    {
        var options = new EndpointOptions { RouteKey = "demo", EnableChatCompletions = true };
        EndpointOptionsValidator.Validate(options);
    }
}

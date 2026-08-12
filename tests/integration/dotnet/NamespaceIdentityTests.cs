using Xunit;
using Ygo74.AgentRuntime;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class NamespaceIdentityTests
{
    [Fact]
    public void NamespaceRoot_Is_Ygo74()
    {
        Assert.Equal("Ygo74", PublicApi.NamespaceRoot);
    }
}

using Xunit;
using Ygo74.AgentRuntime.Domains.Auth;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class AuthorizationDenialTests
{
    [Fact]
    public void AuthErrors_Create_Authorization_Error()
    {
        var err = AuthErrors.Create("forbidden", "authorization", "denied");
        Assert.NotNull(err);
    }
}

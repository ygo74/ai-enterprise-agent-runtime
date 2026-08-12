using Xunit;
using Ygo74.AgentRuntime.Domains.Auth;

namespace Ygo74.AgentRuntime.Tests.Integration;

public sealed class AuthContextTests
{
    [Fact]
    public void JwtAuthenticator_Projects_User_Context()
    {
        var ctx = JwtAuthenticator.Authenticate("token", "user-1");
        Assert.Equal("jwt", ctx["authType"]);
        Assert.Equal("user-1", ctx["userId"]);
    }
}

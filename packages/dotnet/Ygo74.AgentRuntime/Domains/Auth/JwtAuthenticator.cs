namespace Ygo74.AgentRuntime.Domains.Auth;

public static class JwtAuthenticator
{
    public static IDictionary<string, string> Authenticate(string token, string userId)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            throw new ArgumentException("missing token", nameof(token));
        }

        return new Dictionary<string, string>
        {
            ["userId"] = userId,
            ["authType"] = "jwt"
        };
    }
}

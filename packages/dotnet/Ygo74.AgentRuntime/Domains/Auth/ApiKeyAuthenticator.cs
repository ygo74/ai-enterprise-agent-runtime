namespace Ygo74.AgentRuntime.Domains.Auth;

public static class ApiKeyAuthenticator
{
    public static IDictionary<string, string> Authenticate(string apiKey, Func<string, IDictionary<string, string>?> resolver)
    {
        var user = resolver(apiKey);
        if (user is null)
        {
            throw new ArgumentException("invalid api key", nameof(apiKey));
        }

        user["authType"] = "api_key";
        return user;
    }
}

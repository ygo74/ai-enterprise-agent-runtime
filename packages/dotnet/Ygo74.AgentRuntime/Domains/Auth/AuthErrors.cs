namespace Ygo74.AgentRuntime.Domains.Auth;

public static class AuthErrors
{
    public static object Create(string code, string category, string message) => new
    {
        code,
        category,
        message
    };
}

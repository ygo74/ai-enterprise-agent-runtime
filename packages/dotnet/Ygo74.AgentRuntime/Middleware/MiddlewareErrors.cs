namespace Ygo74.AgentRuntime.Middleware;

public static class MiddlewareErrors
{
    public static object Failure(string message) => new
    {
        code = "middleware_failure",
        category = "mapping",
        message
    };
}

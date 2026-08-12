namespace Ygo74.AgentRuntime.Routing;

public static class RoutingErrors
{
    public static object RouteNotRegistered(string routeKey) => new
    {
        code = "route_not_registered",
        category = "routing",
        message = $"No handler registered for route '{routeKey}'"
    };
}

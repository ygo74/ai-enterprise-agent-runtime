using Ygo74.AgentRuntime.Domains.Contracts;

namespace Ygo74.AgentRuntime.Routing;

public sealed class RouteRegistry
{
    private readonly Dictionary<string, UseCaseHandler> _handlers = new();

    public void Register(string routeKey, UseCaseHandler handler)
    {
        if (_handlers.ContainsKey(routeKey))
        {
            throw new ArgumentException("route already registered", nameof(routeKey));
        }

        _handlers[routeKey] = handler;
    }

    public UseCaseHandler Resolve(string routeKey)
    {
        if (!_handlers.TryGetValue(routeKey, out var handler))
        {
            throw new KeyNotFoundException(routeKey);
        }

        return handler;
    }
}

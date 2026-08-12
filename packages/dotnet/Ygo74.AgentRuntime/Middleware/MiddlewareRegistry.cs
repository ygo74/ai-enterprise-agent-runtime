namespace Ygo74.AgentRuntime.Middleware;

public sealed record RegisteredMiddleware(string Id, IMiddleware Middleware, int Order);

public sealed class MiddlewareRegistry
{
    private readonly List<RegisteredMiddleware> _items = new();

    public void Register(string id, IMiddleware middleware, int order)
    {
        _items.Add(new RegisteredMiddleware(id, middleware, order));
    }

    public IReadOnlyList<RegisteredMiddleware> Ordered() => _items.OrderBy(x => x.Order).ToList();
}

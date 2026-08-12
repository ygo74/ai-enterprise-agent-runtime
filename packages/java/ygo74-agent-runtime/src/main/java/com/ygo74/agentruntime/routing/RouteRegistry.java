package com.ygo74.agentruntime.routing;

import java.util.HashMap;
import java.util.Map;

public final class RouteRegistry {
    private final Map<String, Dispatcher.UseCaseHandler> handlers = new HashMap<>();

    public void register(String routeKey, Dispatcher.UseCaseHandler handler) {
        if (handlers.containsKey(routeKey)) {
            throw new IllegalArgumentException("route already registered");
        }
        handlers.put(routeKey, handler);
    }

    public Dispatcher.UseCaseHandler resolve(String routeKey) {
        var handler = handlers.get(routeKey);
        if (handler == null) {
            throw new IllegalArgumentException(routeKey);
        }
        return handler;
    }
}

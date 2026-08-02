package com.ygo74.agentruntime.routing;

import java.util.Map;

public final class RoutingErrors {
    private RoutingErrors() {}

    public static Map<String, String> routeNotRegistered(String routeKey) {
        return Map.of(
                "code", "route_not_registered",
                "category", "routing",
                "message", "No handler registered for route '" + routeKey + "'");
    }
}

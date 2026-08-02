package com.ygo74.agentruntime.middleware;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class MiddlewareRegistry {
    public record Registered(String id, Middleware middleware, int order) {
    }

    private final List<Registered> items = new ArrayList<>();

    public void register(String id, Middleware middleware, int order) {
        items.add(new Registered(id, middleware, order));
    }

    public List<Registered> ordered() {
        return items.stream().sorted(Comparator.comparingInt(Registered::order)).toList();
    }
}

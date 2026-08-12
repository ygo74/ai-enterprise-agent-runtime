package com.ygo74.agentruntime.middleware;

import java.util.Map;

public final class MiddlewareErrors {
    private MiddlewareErrors() {}

    public static Map<String, String> failure(String message) {
        return Map.of(
                "code", "middleware_failure",
                "category", "mapping",
                "message", message);
    }
}

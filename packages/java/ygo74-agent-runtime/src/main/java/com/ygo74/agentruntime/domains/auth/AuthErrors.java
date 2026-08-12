package com.ygo74.agentruntime.domains.auth;

import java.util.Map;

public final class AuthErrors {
    private AuthErrors() {}

    public static Map<String, String> create(String code, String category, String message) {
        return Map.of("code", code, "category", category, "message", message);
    }
}

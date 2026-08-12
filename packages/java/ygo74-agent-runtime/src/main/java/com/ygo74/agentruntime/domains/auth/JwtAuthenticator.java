package com.ygo74.agentruntime.domains.auth;

import java.util.Map;

public final class JwtAuthenticator {
    private JwtAuthenticator() {}

    public static Map<String, String> authenticate(String token, String userId) {
        if (token == null || token.isBlank()) {
            throw new IllegalArgumentException("missing token");
        }

        return Map.of("userId", userId, "authType", "jwt");
    }
}

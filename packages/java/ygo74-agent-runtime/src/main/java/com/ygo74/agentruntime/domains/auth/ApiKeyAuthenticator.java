package com.ygo74.agentruntime.domains.auth;

import java.util.Map;
import java.util.function.Function;

public final class ApiKeyAuthenticator {
    private ApiKeyAuthenticator() {}

    public static Map<String, String> authenticate(String apiKey, Function<String, Map<String, String>> resolver) {
        var user = resolver.apply(apiKey);
        if (user == null) {
            throw new IllegalArgumentException("invalid api key");
        }
        user.put("authType", "api_key");
        return user;
    }
}

package com.ygo74.agentruntime.domains.configuration;

public final class EndpointPropertiesValidator {
    private EndpointPropertiesValidator() {}

    public static void validate(EndpointProperties properties) {
        if (properties.routeKey() == null || properties.routeKey().isBlank()) {
            throw new IllegalArgumentException("routeKey is required");
        }

        if (!properties.enableChatCompletions() && !properties.enableResponses() && !properties.enableAnthropicMessages()) {
            throw new IllegalArgumentException("At least one endpoint surface must be enabled");
        }
    }
}

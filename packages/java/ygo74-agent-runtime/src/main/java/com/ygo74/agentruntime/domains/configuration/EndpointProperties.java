package com.ygo74.agentruntime.domains.configuration;

public record EndpointProperties(
        String routeKey,
        boolean enableChatCompletions,
        boolean enableResponses,
        boolean enableAnthropicMessages,
        boolean enableStreaming) {
}

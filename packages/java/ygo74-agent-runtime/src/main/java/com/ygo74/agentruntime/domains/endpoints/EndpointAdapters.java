package com.ygo74.agentruntime.domains.endpoints;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeRequest;

import java.util.Map;
import java.util.Set;

public final class EndpointAdapters {
    private EndpointAdapters() {}

    private static final Set<String> SUPPORTED = Set.of(
            "openai.chat_completions",
            "openai.responses",
            "anthropic.messages");

    public static StandardExchangeRequest normalize(
            String endpointType,
            String requestId,
            String routeKey,
            Object input,
            boolean stream,
            Map<String, Object> metadata) {

        if (!SUPPORTED.contains(endpointType)) {
            throw new IllegalArgumentException("Unsupported endpoint type: " + endpointType);
        }

        return new StandardExchangeRequest(requestId, routeKey, endpointType, input, stream, metadata, null);
    }
}

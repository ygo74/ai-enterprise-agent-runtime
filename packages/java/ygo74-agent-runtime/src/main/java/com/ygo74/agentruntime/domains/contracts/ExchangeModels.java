package com.ygo74.agentruntime.domains.contracts;

import java.util.Map;

public final class ExchangeModels {
    private ExchangeModels() {}

    public record StandardExchangeRequest(
            String requestId,
            String routeKey,
            String endpointType,
            Object input,
            boolean stream,
            Map<String, Object> metadata,
            Map<String, Object> authContext) {
    }

    public record StandardExchangeResponse(
            String requestId,
            String status,
            Object output,
            ErrorEnvelope error,
            Map<String, Object> metadata) {
    }
}

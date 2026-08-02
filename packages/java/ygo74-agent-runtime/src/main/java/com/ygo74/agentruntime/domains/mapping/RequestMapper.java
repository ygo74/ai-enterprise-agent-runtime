package com.ygo74.agentruntime.domains.mapping;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeRequest;
import com.ygo74.agentruntime.domains.endpoints.EndpointAdapters;

import java.util.Map;

public final class RequestMapper {
    private RequestMapper() {}

    public static StandardExchangeRequest toExchange(
            String endpointType,
            String requestId,
            String routeKey,
            Object input,
            boolean stream,
            Map<String, Object> metadata) {
        return EndpointAdapters.normalize(endpointType, requestId, routeKey, input, stream, metadata);
    }
}

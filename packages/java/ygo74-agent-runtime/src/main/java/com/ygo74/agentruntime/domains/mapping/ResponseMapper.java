package com.ygo74.agentruntime.domains.mapping;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeResponse;

import java.util.HashMap;
import java.util.Map;

public final class ResponseMapper {
    private ResponseMapper() {}

    public static Map<String, Object> toEndpoint(StandardExchangeResponse response) {
        Map<String, Object> mapped = new HashMap<>();
        mapped.put("request_id", response.requestId());
        mapped.put("status", response.status());
        mapped.put("output", response.output());
        mapped.put("error", response.error());
        return mapped;
    }
}

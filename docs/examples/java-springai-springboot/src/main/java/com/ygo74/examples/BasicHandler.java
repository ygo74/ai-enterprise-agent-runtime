package com.ygo74.examples;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeRequest;
import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeResponse;

import java.util.Map;

public class BasicHandler {
    public StandardExchangeResponse handle(StandardExchangeRequest request) {
        return new StandardExchangeResponse(request.requestId(), "success", Map.of("message", "ok"), null, Map.of());
    }
}

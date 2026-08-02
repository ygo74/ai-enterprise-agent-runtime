package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels;
import com.ygo74.agentruntime.domains.handlers.ResponseValidator;
import org.junit.jupiter.api.Test;

import java.util.Map;

class HandlerContractTest {
    @Test
    void responseValidatorAcceptsSuccess() {
        var response = new ExchangeModels.StandardExchangeResponse("r1", "success", Map.of("ok", true), null, Map.of());
        ResponseValidator.validate(response);
    }
}

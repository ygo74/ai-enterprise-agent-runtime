package com.ygo74.agentruntime.domains.handlers;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeResponse;

public final class ResponseValidator {
    private ResponseValidator() {}

    public static void validate(StandardExchangeResponse response) {
        if (!"success".equals(response.status()) && !"error".equals(response.status())) {
            throw new IllegalArgumentException("status must be success or error");
        }
    }
}

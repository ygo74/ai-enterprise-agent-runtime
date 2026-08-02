package com.ygo74.agentruntime.middleware;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeRequest;
import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeResponse;

import java.util.function.Function;

public interface Middleware {
    StandardExchangeResponse invoke(MessagePipelineContext context, Function<MessagePipelineContext, StandardExchangeResponse> next);

    record MessagePipelineContext(StandardExchangeRequest request, StandardExchangeResponse response) {
    }
}

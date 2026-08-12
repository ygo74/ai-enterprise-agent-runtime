package com.ygo74.agentruntime.domains.handlers;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeRequest;
import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeResponse;

public interface UseCaseHandler {
    StandardExchangeResponse handle(StandardExchangeRequest request);
}

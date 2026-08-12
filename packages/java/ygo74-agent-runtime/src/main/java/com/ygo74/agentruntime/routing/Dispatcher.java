package com.ygo74.agentruntime.routing;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeRequest;
import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeResponse;

import java.util.function.Function;

public interface Dispatcher {
    StandardExchangeResponse dispatch(StandardExchangeRequest request, Function<String, UseCaseHandler> resolver);

    interface UseCaseHandler {
        StandardExchangeResponse handle(StandardExchangeRequest request);
    }
}

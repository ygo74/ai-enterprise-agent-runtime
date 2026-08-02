package com.ygo74.agentruntime.routing;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeRequest;
import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeResponse;

import java.util.function.Function;

public final class DispatcherImpl implements Dispatcher {
    @Override
    public StandardExchangeResponse dispatch(StandardExchangeRequest request, Function<String, UseCaseHandler> resolver) {
        return resolver.apply(request.routeKey()).handle(request);
    }
}

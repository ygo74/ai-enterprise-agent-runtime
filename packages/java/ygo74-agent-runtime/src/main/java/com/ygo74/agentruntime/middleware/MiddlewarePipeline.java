package com.ygo74.agentruntime.middleware;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels.StandardExchangeResponse;

import java.util.List;
import java.util.function.Function;

public final class MiddlewarePipeline {
    private MiddlewarePipeline() {}

    public static StandardExchangeResponse execute(
            Middleware.MessagePipelineContext context,
            List<Middleware> middlewares,
            Function<Middleware.MessagePipelineContext, StandardExchangeResponse> handler) {
        return chain(0, context, middlewares, handler);
    }

    private static StandardExchangeResponse chain(
            int index,
            Middleware.MessagePipelineContext context,
            List<Middleware> middlewares,
            Function<Middleware.MessagePipelineContext, StandardExchangeResponse> handler) {
        if (index >= middlewares.size()) {
            return handler.apply(context);
        }

        return middlewares.get(index).invoke(context, next -> chain(index + 1, next, middlewares, handler));
    }
}

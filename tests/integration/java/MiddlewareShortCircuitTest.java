package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels;
import com.ygo74.agentruntime.middleware.Middleware;
import com.ygo74.agentruntime.middleware.MiddlewarePipeline;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class MiddlewareShortCircuitTest {
    @Test
    void pipelineShortCircuit() {
        var req = new ExchangeModels.StandardExchangeRequest("r1", "demo", "openai.responses", "hi", false, Map.of(), null);
        var ctx = new Middleware.MessagePipelineContext(req, null);
        Middleware shortMw = (c, next) -> new ExchangeModels.StandardExchangeResponse("r1", "success", "short", null, Map.of());
        var out = MiddlewarePipeline.execute(ctx, List.of(shortMw), c -> new ExchangeModels.StandardExchangeResponse("r1", "success", "handler", null, Map.of()));
        assertEquals("short", out.output());
    }
}

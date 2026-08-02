package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels;
import com.ygo74.agentruntime.middleware.Middleware;
import com.ygo74.agentruntime.middleware.MiddlewarePipeline;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class MiddlewarePipelineTest {
    @Test
    void pipelineExecutesHandler() {
        var req = new ExchangeModels.StandardExchangeRequest("r1", "demo", "openai.responses", "hi", false, Map.of(), null);
        var ctx = new Middleware.MessagePipelineContext(req, null);
        Middleware pass = (c, next) -> next.apply(c);
        var out = MiddlewarePipeline.execute(ctx, List.of(pass), c -> new ExchangeModels.StandardExchangeResponse("r1", "success", "ok", null, Map.of()));
        assertEquals("success", out.status());
    }
}

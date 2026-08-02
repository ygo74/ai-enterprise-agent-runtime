package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.contracts.ExchangeModels;
import com.ygo74.agentruntime.routing.DispatcherImpl;
import com.ygo74.agentruntime.routing.RouteRegistry;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DispatchRoutingTest {
    @Test
    void dispatchUsesRegisteredHandler() {
        var reg = new RouteRegistry();
        reg.register("demo", req -> new ExchangeModels.StandardExchangeResponse(req.requestId(), "success", Map.of("ok", true), null, Map.of()));
        var dispatcher = new DispatcherImpl();
        var out = dispatcher.dispatch(new ExchangeModels.StandardExchangeRequest("r1", "demo", "openai.responses", "hi", false, Map.of(), null), reg::resolve);
        assertEquals("success", out.status());
    }
}

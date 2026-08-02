package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.endpoints.EndpointAdapters;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class MetadataPreservationTest {
    @Test
    void metadataPreserved() {
        var req = EndpointAdapters.normalize("openai.responses", "r1", "demo", "hi", false, Map.of("model", "gpt-x"));
        assertEquals("gpt-x", req.metadata().get("model"));
    }
}

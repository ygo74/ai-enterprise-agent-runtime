package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.streaming.AnthropicStreamMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class StreamingEndpointsTest {
    @Test
    void streamChunkMapped() {
        var evt = AnthropicStreamMapper.mapChunk("r1", 1, "a");
        assertEquals("chunk", evt.eventType());
    }
}

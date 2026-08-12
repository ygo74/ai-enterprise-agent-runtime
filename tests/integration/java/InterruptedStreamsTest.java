package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.contracts.ErrorEnvelope;
import com.ygo74.agentruntime.domains.streaming.StreamTermination;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class InterruptedStreamsTest {
    @Test
    void interruptedStreamToErrorEvent() {
        var err = new ErrorEnvelope("stream_interrupted", "mapping", "x", null, null, null);
        var evt = StreamTermination.error("r1", 2, err);
        assertEquals("error", evt.eventType());
    }
}

package com.ygo74.agentruntime.domains.streaming;

import com.ygo74.agentruntime.domains.contracts.ErrorEnvelope;
import com.ygo74.agentruntime.domains.contracts.StreamingEvent;

public final class StreamTermination {
    private StreamTermination() {}

    public static StreamingEvent completion(String requestId, int sequence, Object finalOutput) {
        return new StreamingEvent(requestId, sequence, "completion", null, finalOutput, null);
    }

    public static StreamingEvent error(String requestId, int sequence, ErrorEnvelope error) {
        return new StreamingEvent(requestId, sequence, "error", null, null, error);
    }
}

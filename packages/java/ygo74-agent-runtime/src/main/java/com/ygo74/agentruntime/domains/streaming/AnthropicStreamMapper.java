package com.ygo74.agentruntime.domains.streaming;

import com.ygo74.agentruntime.domains.contracts.StreamingEvent;

public final class AnthropicStreamMapper {
    private AnthropicStreamMapper() {}

    public static StreamingEvent mapChunk(String requestId, int sequence, Object delta) {
        return new StreamingEvent(requestId, sequence, "chunk", delta, null, null);
    }
}

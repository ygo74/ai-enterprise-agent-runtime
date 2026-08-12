package com.ygo74.agentruntime.domains.contracts;

public record StreamingEvent(
        String requestId,
        int sequence,
        String eventType,
        Object delta,
        Object finalOutput,
        ErrorEnvelope error) {
}

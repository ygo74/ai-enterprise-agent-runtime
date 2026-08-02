package com.ygo74.agentruntime.domains.contracts;

public record ErrorEnvelope(
        String code,
        String category,
        String message,
        Object details,
        String requestId,
        Boolean retryable) {
}

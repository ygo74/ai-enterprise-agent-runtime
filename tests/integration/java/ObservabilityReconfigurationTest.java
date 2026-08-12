package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.observability.OpenTelemetrySetup;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ObservabilityReconfigurationTest {
    @Test
    void observabilityExporterSelection() {
        assertEquals("otlp", OpenTelemetrySetup.configureExporter("otlp"));
    }
}

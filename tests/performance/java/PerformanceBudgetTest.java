package com.ygo74.agentruntime.performance;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertTrue;

class PerformanceBudgetTest {
    @Test
    void baselineFileExists() {
        assertTrue(Files.exists(Path.of("tests/performance/baselines/performance_thresholds.json")));
    }
}

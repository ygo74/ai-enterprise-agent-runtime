package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.PublicApi;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class NamespaceIdentityTest {
    @Test
    void namespaceIdentity() {
        assertEquals("ygo74", PublicApi.namespaceRoot());
    }
}

package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.auth.AuthErrors;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AuthorizationDenialTest {
    @Test
    void authorizationErrorShape() {
        var err = AuthErrors.create("forbidden", "authorization", "denied");
        assertEquals("authorization", err.get("category"));
    }
}

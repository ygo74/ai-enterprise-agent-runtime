package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.auth.JwtAuthenticator;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AuthContextTest {
    @Test
    void jwtAuthContext() {
        var ctx = JwtAuthenticator.authenticate("token", "user-1");
        assertEquals("jwt", ctx.get("authType"));
    }
}

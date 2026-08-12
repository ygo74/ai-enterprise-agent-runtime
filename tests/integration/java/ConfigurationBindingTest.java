package com.ygo74.agentruntime.integration;

import com.ygo74.agentruntime.domains.configuration.EndpointProperties;
import com.ygo74.agentruntime.domains.configuration.EndpointPropertiesValidator;
import org.junit.jupiter.api.Test;

class ConfigurationBindingTest {
    @Test
    void configurationValidates() {
        EndpointPropertiesValidator.validate(new EndpointProperties("demo", true, false, false, false));
    }
}

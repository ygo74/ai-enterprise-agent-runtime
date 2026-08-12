package com.ygo74.agentruntime.observability;

import java.util.logging.Level;
import java.util.logging.Logger;

public final class LoggingSetup {
    private LoggingSetup() {}

    public static Logger configure(String loggerName, Level level) {
        Logger logger = Logger.getLogger(loggerName);
        logger.setLevel(level);
        return logger;
    }
}

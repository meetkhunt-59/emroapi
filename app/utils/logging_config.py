import logging
import json
from datetime import datetime
from os import getenv
import sys

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

def setup_logging():
    log_level = getenv("LOG_LEVEL", "INFO")
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # File handler for persistent logs
    file_handler = logging.FileHandler("app.log")
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    # Disable/Filter uvicorn access logs (e.g., GET /metrics)
    class _IgnoreMetricsFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            return "/metrics" not in msg

    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(logging.WARNING)  # raise threshold
    uvicorn_access.propagate = False
    uvicorn_access.handlers = []
    # Add a minimal handler only if needed by framework defaults
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_IgnoreMetricsFilter())
    uvicorn_access.addHandler(handler)
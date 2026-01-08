import logging
import structlog

# One-time configuration at import
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

def get_logger(name: str):
    return structlog.get_logger(name)

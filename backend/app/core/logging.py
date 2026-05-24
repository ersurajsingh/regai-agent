import logging
import sys
from app.core.config import settings


def setup_logging() -> None:
    """Configure structured JSON-style logging for the application."""
    level = logging.DEBUG if settings.APP_ENV == "development" else logging.INFO

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "motor", "pymongo", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

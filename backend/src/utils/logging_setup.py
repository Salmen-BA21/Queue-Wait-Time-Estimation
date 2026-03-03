"""
Logging configuration for the queue estimation system.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure and return the root application logger.

    Parameters
    ----------
    level : str
        Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    log_file : str | None
        If provided, logs are also written to this file.

    Returns
    -------
    logging.Logger
        Configured root logger for the application.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    fmt = "%(asctime)s │ %(levelname)-8s │ %(name)-22s │ %(message)s"
    date_fmt = "%H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=numeric_level,
        format=fmt,
        datefmt=date_fmt,
        handlers=handlers,
        force=True,
    )

    # Silence noisy third-party loggers
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("supervision").setLevel(logging.WARNING)

    logger = logging.getLogger("queue_system")
    logger.setLevel(numeric_level)
    logger.info("Logging initialised – level=%s", level.upper())
    return logger

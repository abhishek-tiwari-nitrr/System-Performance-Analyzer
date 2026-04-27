import logging, os
from src.config.config import LOG_DIR


def _setup_logs() -> logging.Logger:
    """
    Logging configuration for the application.

    This module defines and initializes a singleton logger instance named "SPA". The logger writes log messages to a file located in the directory specified by LOG_DIR, creating the directory if it does not already exist

    Logging Configuration:
            - File Path: ./logs/app.log
            - Mode: Append (`a`)
            - Level: INFO
            - Format: Timestamp | Level | Message
            - Date Format: YYYY-MM-DD HH:MM:SS
    
    Returns:
        - logging.Logger: A configured logger instance named "SPA"
    """
    log = logging.getLogger("SPA")
    if log.handlers:
        return log

    os.makedirs(LOG_DIR, exist_ok=True)

    handler = logging.FileHandler(LOG_DIR / "app.log", mode="a", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    return log


logger = _setup_logs()

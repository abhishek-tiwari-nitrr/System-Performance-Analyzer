import logging, os
from src.config.config import LOG_DIR


class Logger:
    """
    A utility class for setting up structured file-based logging.
    On initialization, it ensures that a `logs/` directory exists

    Attributes: None

    Methods:
        setup_logs(): Configures logging settings and returns a logger instance

    """

    def __init__(self):
        """
        Initialize the Logger class.
        Creates the `logs/` directory if it does not already exist
        """
        os.makedirs(LOG_DIR, exist_ok=True)

    def setup_logs(self):
        """
        Configure the logging system and return a named logger.

        Logging Configuration:
            - File Path: ./logs/app.log
            - Mode: Append (`a`)
            - Level: INFO
            - Format: Timestamp | Level | Message
            - Date Format: YYYY-MM-DD HH:MM:SS

        Returns:
            logging.Logger: A configured logger instance named `SPA`

        Example:
            logger = Logger().setup_logs()
            logger.info("This is an info message")
        """
        logging.basicConfig(
            filename="./logs/app.log",
            filemode="a",
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return logging.getLogger("SPA")

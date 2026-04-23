import logging, os
from src.config.config import LOG_DIR


class Logger:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)

    def setup_logs(self):
        logging.basicConfig(
            filename="./logs/app.log",
            filemode="a",
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return logging.getLogger("SPA")

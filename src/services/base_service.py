from abc import ABC, abstractmethod
from src.logger.logger import Logger

logger = Logger().setup_logs()


class BaseService(ABC):
    def run_collect(self):
        logger.info(f"{self.__class__.__name__}: collect() called")
        return self.collect()

    @abstractmethod
    def collect(self):
        pass

from abc import ABC, abstractmethod
from src.logger.logger import logger


class BaseService(ABC):
    """
    Abstract base class for all service collectors.

    This class ensures that every subclass implements the `collect()` method while providing a common `run_collect()` method that handles logging before executing the collection process

    Methods:
        run_collect(): Logs execution and calls the subclass `collect()` method

        collect(): Abstract method that must be implemented by subclasses
    """

    def run_collect(self):
        """
        Execute the collection workflow with logging.
        Logs the class name and invokes the subclass-defined `collect()` method

        Returns:
            Any: Result returned by the subclass implementation.
        """
        logger.info(f"{self.__class__.__name__}: collect() called")
        return self.collect()

    @abstractmethod
    def collect(self):
        """
        Define the data collection logic.
        This method must be implemented by all subclasses.

        Returns:
            Any: Depends on subclass implementation.
        """

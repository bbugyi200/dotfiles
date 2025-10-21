from abc import ABC, abstractmethod


class BaseWorkflow(ABC):
    """Base class for all GAI workflows."""

    @abstractmethod
    def run(self) -> bool:
        """
        Run the workflow.

        Returns:
            bool: True if the workflow completed successfully, False otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this workflow."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what this workflow does."""
        pass

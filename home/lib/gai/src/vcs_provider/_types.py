"""Internal data types for VCS provider implementations."""

from dataclasses import dataclass


@dataclass
class CommandOutput:
    """Result of running a VCS subprocess command.

    Used internally by provider implementations only, not exposed to consumers.
    """

    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Whether the command succeeded (returncode == 0)."""
        return self.returncode == 0

"""Custom exceptions for VCS provider operations."""


class VCSOperationError(Exception):
    """Raised when a VCS operation fails."""

    def __init__(self, operation: str, message: str) -> None:
        self.operation = operation
        self.message = message
        super().__init__(f"{operation}: {message}")


class VCSProviderNotFoundError(Exception):
    """Raised when no VCS provider can be detected for a directory."""

    def __init__(self, directory: str) -> None:
        self.directory = directory
        super().__init__(f"No VCS provider found for directory: {directory}")

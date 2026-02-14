"""Functions for retrieving branch and CL information."""

import os

from vcs_provider import get_vcs_provider


def get_parent_branch_name(cwd: str | None = None) -> str | None:
    """Get the parent branch name using the VCS provider.

    Args:
        cwd: Working directory for VCS detection. Defaults to os.getcwd().

    Returns:
        The parent branch name, or None if the command fails or returns empty.
    """
    effective_cwd = cwd if cwd is not None else os.getcwd()
    provider = get_vcs_provider(effective_cwd)
    success, result = provider.get_branch_name(effective_cwd)
    if not success:
        return None
    parent_name = result.strip() if result else None
    return parent_name if parent_name else None


def get_cl_number(cwd: str | None = None) -> str | None:
    """Get the CL number using the VCS provider.

    Args:
        cwd: Working directory for VCS detection. Defaults to os.getcwd().

    Returns:
        The CL number, or None if the command fails.
    """
    effective_cwd = cwd if cwd is not None else os.getcwd()
    provider = get_vcs_provider(effective_cwd)
    success, result = provider.get_cl_number(effective_cwd)
    if not success:
        return None
    cl_number = result.strip() if result else None
    return cl_number if cl_number and cl_number.isdigit() else None

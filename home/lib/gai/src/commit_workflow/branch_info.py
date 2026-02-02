"""Functions for retrieving branch and CL information."""

from shared_utils import run_shell_command


def get_parent_branch_name() -> str | None:
    """Get the parent branch name using the branch_name command.

    Returns:
        The parent branch name, or None if the command fails or returns empty.
    """
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        return None
    parent_name = result.stdout.strip()
    return parent_name if parent_name else None


def get_cl_number() -> str | None:
    """Get the CL number using the branch_number command.

    Returns:
        The CL number, or None if the command fails.
    """
    result = run_shell_command("branch_number", capture_output=True)
    if result.returncode != 0:
        return None
    cl_number = result.stdout.strip()
    return cl_number if cl_number and cl_number.isdigit() else None

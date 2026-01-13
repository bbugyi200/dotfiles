import os
import random
import string
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from gai_utils import EASTERN_TZ, run_shell_command
from rich_utils import (
    print_file_operation,
    print_status,
    print_workflow_header,
)

# LangGraph configuration
LANGGRAPH_RECURSION_LIMIT = 100


@dataclass
class WorkflowContext:
    """Context for a workflow run.

    Contains the workflow metadata generated during initialization,
    including the unique tag and artifacts directory path.
    """

    workflow_tag: str
    artifacts_dir: str
    workflow_name: str


def ensure_str_content(content: str | list[str | dict[Any, Any]]) -> str:
    """Ensure AIMessage content is a string.

    AIMessage.content can be either a string or a list of content parts.
    This function ensures we always get a string representation.
    """
    if isinstance(content, str):
        return content
    # Handle list content by converting to string
    return str(content)


def create_artifacts_directory(
    workflow_name: str, project_name: str | None = None
) -> str:
    """Create a timestamped artifacts directory using NYC Eastern timezone.

    Args:
        workflow_name: Name of the workflow (e.g., 'crs', 'new-tdd-feature')
        project_name: Name of the project. If None, will attempt to get from workspace_name command

    Returns:
        Path to the created artifacts directory: ~/.gai/projects/<project>/artifacts/<workflow>/<timestamp>
    """
    timestamp = datetime.now(EASTERN_TZ).strftime("%Y%m%d%H%M%S")

    # Get project name from workspace_name command if not provided
    if project_name is None:
        result = run_shell_command("workspace_name", capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to get project name from workspace_name: {result.stderr}"
            )
        project_name = result.stdout.strip()

    # Create artifacts directory in new location: ~/.gai/projects/<project>/artifacts/<workflow>/<timestamp>
    artifacts_dir = os.path.expanduser(
        f"~/.gai/projects/{project_name}/artifacts/{workflow_name}/{timestamp}"
    )
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def generate_workflow_tag() -> str:
    """Generate a unique 3-digit alphanumeric tag for the workflow run."""
    # Use digits and uppercase letters for better readability
    chars = string.digits + string.ascii_uppercase
    return "".join(random.choices(chars, k=3))


def initialize_workflow(workflow_name: str) -> WorkflowContext:
    """Initialize a workflow with standard boilerplate.

    Creates artifacts directory, prints workflow header, and initializes
    the gai.md log file.

    Args:
        workflow_name: Name of the workflow (e.g., "qa", "crs", "crs").

    Returns:
        WorkflowContext with workflow_tag and artifacts_dir.
    """
    workflow_tag = generate_workflow_tag()
    print_workflow_header(workflow_name, workflow_tag)
    print_status(f"Initializing {workflow_name} workflow", "info")
    artifacts_dir = create_artifacts_directory(workflow_name)
    print_status(f"Created artifacts directory: {artifacts_dir}", "success")
    initialize_gai_log(artifacts_dir, workflow_name, workflow_tag)
    return WorkflowContext(
        workflow_tag=workflow_tag,
        artifacts_dir=artifacts_dir,
        workflow_name=workflow_name,
    )


def run_bam_command(message: str, delay: float = 0.1) -> None:
    """Run bam command to signal completion.

    Args:
        message: Message to display with the bam notification
        delay: Delay in seconds for the bam sound (default: 0.1)
    """
    try:
        run_shell_command(f'bam 3 {delay} "{message}"', capture_output=False)
    except Exception as e:
        print(f"Warning: Failed to run bam command: {e}")


def get_gai_log_file(artifacts_dir: str) -> str:
    """Get the path to the workflow-specific gai.md log file."""
    return os.path.join(artifacts_dir, "gai.md")


def _initialize_log_file(log_file: str, content: str, operation_name: str) -> None:
    """Write initial content to a log file.

    Args:
        log_file: Path to the log file to create.
        content: The formatted content to write.
        operation_name: Name for print_file_operation message.
    """
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(content)
        print_file_operation(operation_name, log_file, True)
    except Exception as e:
        print_status(f"Failed to initialize {operation_name.lower()}: {e}", "warning")


def _finalize_log_file(log_file: str, content: str, operation_name: str) -> None:
    """Append final content to a log file.

    Args:
        log_file: Path to the log file to append to.
        content: The formatted content to append.
        operation_name: Name for print_file_operation message.
    """
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(content)
        print_file_operation(operation_name, log_file, True)
    except Exception as e:
        print_status(f"Failed to finalize {operation_name.lower()}: {e}", "warning")


def initialize_gai_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str
) -> None:
    """Initialize the gai.md log file for a new workflow run.

    Args:
        artifacts_dir: Directory where the gai.md file should be stored
        workflow_name: Name of the workflow (e.g., "crs", "add-tests")
        workflow_tag: Unique workflow tag
    """
    log_file = get_gai_log_file(artifacts_dir)
    timestamp = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S EST")

    content = f"""# GAI Workflow Log - {workflow_name} ({workflow_tag})

Started: {timestamp}
Artifacts Directory: {artifacts_dir}

"""
    _initialize_log_file(log_file, content, "Initialized GAI log")


def finalize_gai_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str, success: bool
) -> None:
    """Finalize the gai.md log file for a completed workflow run.

    Args:
        artifacts_dir: Directory where the gai.md file is stored
        workflow_name: Name of the workflow
        workflow_tag: Unique workflow tag
        success: Whether the workflow completed successfully
    """
    log_file = get_gai_log_file(artifacts_dir)
    timestamp = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S EST")
    status = "SUCCESS" if success else "FAILED"

    content = f"""
## Workflow Completed - {timestamp}

**Status:** {status}
**Workflow:** {workflow_name}
**Tag:** {workflow_tag}
**Artifacts Directory:** {artifacts_dir}

===============================================================================

"""
    _finalize_log_file(log_file, content, "Finalized GAI log")

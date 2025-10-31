import os
import random
import string
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from rich_utils import print_command_execution, print_file_operation, print_status

# LangGraph configuration
LANGGRAPH_RECURSION_LIMIT = 100


def run_shell_command(
    cmd: str, capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True,
    )


def run_shell_command_with_input(
    cmd: str, input_text: str, capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command with input text and return the result."""
    return subprocess.run(
        cmd,
        shell=True,
        input=input_text,
        capture_output=capture_output,
        text=True,
    )


def create_artifacts_directory() -> str:
    """Create a timestamped artifacts directory using NYC Eastern timezone."""
    eastern = ZoneInfo("America/New_York")
    timestamp = datetime.now(eastern).strftime("%Y%m%d%H%M%S")
    artifacts_dir = f"bb/gai/{timestamp}"
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def has_uncommitted_changes() -> bool:
    """Check if there are any uncommitted changes using hg diff."""
    try:
        result = run_shell_command("hg diff", capture_output=True)
        return bool(result.stdout.strip())
    except Exception as e:
        print(f"Warning: Failed to check for uncommitted changes: {e}")
        return False


def safe_hg_amend(commit_message: str, use_unamend_first: bool = False) -> bool:
    """
    Safely run hg amend with proper error handling and safeguards.

    Args:
        commit_message: The commit message to use
        use_unamend_first: Whether to run unamend before amend (for subsequent amends)

    Returns:
        bool: True if successful, False if failed
    """
    # Check if there are any uncommitted changes
    if not has_uncommitted_changes():
        print_status("No uncommitted changes detected - skipping hg amend", "warning")
        return True  # Not an error condition, just nothing to commit

    try:
        if use_unamend_first:
            # First run unamend
            print_status("Running hg unamend before amend...", "progress")
            unamend_result = run_shell_command("hg unamend", capture_output=True)
            if unamend_result.returncode != 0:
                print_command_execution("hg unamend", False, unamend_result.stderr)
                return False
            print_status("hg unamend successful", "success")

        # Run the amend command
        amend_cmd = f"hg amend -n '{commit_message}'"
        print_command_execution(amend_cmd, True)
        amend_result = run_shell_command(amend_cmd, capture_output=True)

        if amend_result.returncode == 0:
            print_status(f"hg amend successful: {commit_message}", "success")
            return True
        else:
            print_command_execution(amend_cmd, False, amend_result.stderr)
            return False

    except Exception as e:
        print_status(f"Error during hg amend operation: {e}", "error")
        return False


def generate_workflow_tag() -> str:
    """Generate a unique 3-digit alphanumeric tag for the workflow run."""
    # Use digits and uppercase letters for better readability
    chars = string.digits + string.ascii_uppercase
    return "".join(random.choices(chars, k=3))


def run_bam_command(message: str) -> None:
    """Run bam command to signal completion."""
    try:
        run_shell_command(f'bam 3 0.1 "{message}"', capture_output=False)
    except Exception as e:
        print(f"Warning: Failed to run bam command: {e}")


def _get_gai_log_file(artifacts_dir: str) -> str:
    """Get the path to the workflow-specific gai.md log file."""
    return os.path.join(artifacts_dir, "gai.md")


def initialize_gai_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str
) -> None:
    """
    Initialize the gai.md log file for a new workflow run.

    Args:
        artifacts_dir: Directory where the gai.md file should be stored
        workflow_name: Name of the workflow (e.g., "fix-tests", "add-tests")
        workflow_tag: Unique workflow tag
    """
    try:
        log_file = _get_gai_log_file(artifacts_dir)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        # Create initialization entry
        init_entry = f"""# GAI Workflow Log - {workflow_name} ({workflow_tag})

Started: {timestamp}
Artifacts Directory: {artifacts_dir}

"""

        # Create the file (should be new for each workflow run)
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(init_entry)

        print_file_operation("Initialized GAI log", log_file, True)

    except Exception as e:
        print_status(f"Failed to initialize gai.md log: {e}", "warning")


def finalize_gai_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str, success: bool
) -> None:
    """
    Finalize the gai.md log file for a completed workflow run.

    Args:
        artifacts_dir: Directory where the gai.md file is stored
        workflow_name: Name of the workflow
        workflow_tag: Unique workflow tag
        success: Whether the workflow completed successfully
    """
    try:
        log_file = _get_gai_log_file(artifacts_dir)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        status = "SUCCESS" if success else "FAILED"

        final_entry = f"""
## Workflow Completed - {timestamp}

**Status:** {status}  
**Workflow:** {workflow_name}  
**Tag:** {workflow_tag}  
**Artifacts Directory:** {artifacts_dir}

===============================================================================

"""

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(final_entry)

        print_file_operation("Finalized GAI log", log_file, True)

    except Exception as e:
        print_status(f"Failed to finalize gai.md log: {e}", "warning")


def _get_workflow_log_file(artifacts_dir: str) -> str:
    """Get the path to the workflow log.md file."""
    return os.path.join(artifacts_dir, "log.md")


def initialize_workflow_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str
) -> None:
    """
    Initialize the log.md file for a new workflow run.

    Args:
        artifacts_dir: Directory where the log.md file should be stored
        workflow_name: Name of the workflow (e.g., "fix-tests", "add-tests")
        workflow_tag: Unique workflow tag
    """
    try:
        log_file = _get_workflow_log_file(artifacts_dir)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        # Create initialization entry
        init_entry = f"""# {workflow_name.title()} Workflow Log ({workflow_tag})

**Started:** {timestamp}  
**Artifacts Directory:** {artifacts_dir}

This log contains all planning, research, and test output information organized by iteration.

"""

        # Create the file (should be new for each workflow run)
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(init_entry)

        print_file_operation("Initialized workflow log", log_file, True)

    except Exception as e:
        print_status(f"Failed to initialize log.md: {e}", "warning")


def _append_to_workflow_log(artifacts_dir: str, content: str) -> None:
    """Append content to the workflow log file."""
    try:
        log_file = _get_workflow_log_file(artifacts_dir)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print_status(f"Failed to append to log.md: {e}", "warning")


def add_test_output_to_log(
    artifacts_dir: str,
    iteration: int,
    test_output: str = None,
    test_output_is_meaningful: bool = True,
) -> None:
    """
    Add just the test output section to the workflow log for the current iteration.
    This should be called immediately after running tests.

    Args:
        artifacts_dir: Directory where the log.md file is stored
        iteration: Iteration number
        test_output: Test output (only if meaningful change or first iteration)
        test_output_is_meaningful: Whether test output represents a meaningful change
    """
    try:
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        section_content = f"""
## Iteration {iteration} - {timestamp}

"""

        # Add test output section
        if test_output_is_meaningful and test_output:
            section_content += f"""### Test Output

```
{test_output}
```

"""
        elif not test_output_is_meaningful:
            section_content += """### Test Output

No meaningful change to test output.

"""

        _append_to_workflow_log(artifacts_dir, section_content)
        print_status(
            f"Added test output for iteration {iteration} to workflow log", "success"
        )

    except Exception as e:
        print_status(
            f"Failed to add test output for iteration {iteration} to log.md: {e}",
            "warning",
        )


def add_iteration_section_to_log(
    artifacts_dir: str,
    iteration: int,
    planner_response: str = None,
    todos_content: str = None,
    test_output: str = None,
    test_output_is_meaningful: bool = True,
    research_content: str = None,
    postmortem_content: str = None,
) -> None:
    """
    Add planning, research, and postmortem content to the workflow log.
    Note: Test output should be added separately using add_test_output_to_log().

    Args:
        artifacts_dir: Directory where the log.md file is stored
        iteration: Iteration number (used only for logging messages)
        planner_response: The planner agent's response
        todos_content: The todos produced by the planner
        test_output: DEPRECATED - test output should be added via add_test_output_to_log()
        test_output_is_meaningful: DEPRECATED - not used anymore
        research_content: Research findings (if test output was meaningful)
        postmortem_content: Postmortem analysis (if test output was not meaningful)
    """
    try:
        section_content = ""

        # Add planner response if provided
        if planner_response:
            section_content += f"""### Planner Agent Response

{planner_response}

"""

        # Add todos if provided
        if todos_content:
            section_content += f"""### Generated Todos

```markdown
{todos_content}
```

"""

        # Add research or postmortem content
        if research_content:
            section_content += f"""### Research Findings

{research_content}

"""
        elif postmortem_content:
            section_content += f"""### Iteration Postmortem

{postmortem_content}

"""

        section_content += "---\n\n"

        _append_to_workflow_log(artifacts_dir, section_content)
        print_status(
            f"Added planning content for iteration {iteration} to workflow log",
            "success",
        )

    except Exception as e:
        print_status(
            f"Failed to add planning content for iteration {iteration} to log.md: {e}",
            "warning",
        )


def finalize_workflow_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str, success: bool
) -> None:
    """
    Finalize the log.md file for a completed workflow run.

    Args:
        artifacts_dir: Directory where the log.md file is stored
        workflow_name: Name of the workflow
        workflow_tag: Unique workflow tag
        success: Whether the workflow completed successfully
    """
    try:
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        status = "SUCCESS" if success else "FAILED"

        final_entry = f"""
## Workflow Completed - {timestamp}

**Status:** {status}  
**Workflow:** {workflow_name}  
**Tag:** {workflow_tag}

===============================================================================

"""

        _append_to_workflow_log(artifacts_dir, final_entry)
        print_file_operation(
            "Finalized workflow log", _get_workflow_log_file(artifacts_dir), True
        )

    except Exception as e:
        print_status(f"Failed to finalize log.md: {e}", "warning")

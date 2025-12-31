import os
import random
import string
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from rich_utils import print_command_execution, print_file_operation, print_status

# LangGraph configuration
LANGGRAPH_RECURSION_LIMIT = 100


def ensure_str_content(content: str | list[str | dict[Any, Any]]) -> str:
    """
    Ensure AIMessage content is a string.

    AIMessage.content can be either a string or a list of content parts.
    This function ensures we always get a string representation.
    """
    if isinstance(content, str):
        return content
    # Handle list content by converting to string
    return str(content)


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


def create_artifacts_directory(
    workflow_name: str, project_name: str | None = None
) -> str:
    """Create a timestamped artifacts directory using NYC Eastern timezone.

    Args:
        workflow_name: Name of the workflow (e.g., 'fix-tests', 'new-tdd-feature')
        project_name: Name of the project. If None, will attempt to get from workspace_name command

    Returns:
        Path to the created artifacts directory: ~/.gai/projects/<project>/artifacts/<workflow>/<timestamp>
    """
    eastern = ZoneInfo("America/New_York")
    timestamp = datetime.now(eastern).strftime("%Y%m%d%H%M%S")

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


def _has_uncommitted_changes() -> bool:
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
    if not _has_uncommitted_changes():
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
        amend_cmd = f"bb_hg_amend '{commit_message}'"
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
        log_file = get_gai_log_file(artifacts_dir)
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
        log_file = get_gai_log_file(artifacts_dir)
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


def _get_tests_log_file(artifacts_dir: str) -> str:
    """Get the path to the workflow tests.md file."""
    return os.path.join(artifacts_dir, "tests.md")


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


def initialize_tests_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str
) -> None:
    """
    Initialize the tests.md file for a new workflow run.

    Args:
        artifacts_dir: Directory where the tests.md file should be stored
        workflow_name: Name of the workflow (e.g., "fix-tests", "add-tests")
        workflow_tag: Unique workflow tag
    """
    try:
        tests_file = _get_tests_log_file(artifacts_dir)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        # Create initialization entry
        init_entry = f"""# {workflow_name.title()} Tests Log ({workflow_tag})

**Started:** {timestamp}  
**Artifacts Directory:** {artifacts_dir}

This log contains only test output information organized by iteration.

"""

        # Create the file (should be new for each workflow run)
        with open(tests_file, "w", encoding="utf-8") as f:
            f.write(init_entry)

        print_file_operation("Initialized tests log", tests_file, True)

    except Exception as e:
        print_status(f"Failed to initialize tests.md: {e}", "warning")


def _append_to_workflow_log(artifacts_dir: str, content: str) -> None:
    """Append content to the workflow log file."""
    try:
        log_file = _get_workflow_log_file(artifacts_dir)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print_status(f"Failed to append to log.md: {e}", "warning")


def _append_to_tests_log(artifacts_dir: str, content: str) -> None:
    """Append content to the tests log file."""
    try:
        tests_file = _get_tests_log_file(artifacts_dir)
        with open(tests_file, "a", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print_status(f"Failed to append to tests.md: {e}", "warning")


def extract_section(content: str, section_name: str) -> str:
    """
    Extract a specific ### section from agent output.
    Everything outside the specified section is discarded.

    Args:
        content: Full agent response content
        section_name: Name of section to extract (e.g., "Research", "Test Fixer Log", "Postmortem")

    Returns:
        Content from the specified section only, or original content if no section found
    """
    lines = content.split("\n")
    section_lines = []
    in_section = False

    for line in lines:
        # Check if we're entering the target section
        if line.strip().startswith(f"### {section_name}"):
            in_section = True
            continue  # Don't include the ### header itself

        # Check if we're entering a different ### section (exits current section)
        elif line.strip().startswith("### ") and in_section:
            break

        # If we're in the section, collect the line
        if in_section:
            section_lines.append(line)

    # If we found the section, return it; otherwise return original content
    if section_lines:
        return "\n".join(section_lines).strip()
    else:
        # Fallback: if no section found, return original content
        # This maintains backward compatibility with old agent responses
        return content


def _extract_research_section(content: str) -> str:
    """
    Extract only the ### Research section from research agent output.
    Everything outside the ### Research section is discarded.

    Args:
        content: Full agent response content

    Returns:
        Content from the ### Research section only, or original content if no section found
    """
    return extract_section(content, "Research")


def _normalize_research_headers(content: str) -> str:
    """
    Normalize research agent headers to be nested properly under ### Research Findings.
    Converts ## headers to #### headers, ### to #####, etc.
    """
    lines = content.split("\n")
    normalized_lines = []

    for line in lines:
        # Add two # characters to existing headers to make them deeper
        if line.startswith("## "):
            normalized_lines.append("####" + line[2:])
        elif line.startswith("### "):
            normalized_lines.append("#####" + line[3:])
        elif line.startswith("#### "):
            normalized_lines.append("######" + line[4:])
        elif line.startswith("# "):
            normalized_lines.append("###" + line[1:])
        else:
            normalized_lines.append(line)

    return "\n".join(normalized_lines)


def add_postmortem_to_log(
    artifacts_dir: str,
    iteration: int,
    postmortem_content: str,
) -> None:
    """
    Add postmortem analysis section to the workflow log for the current iteration.
    This should be called immediately after postmortem agent completes.

    Args:
        artifacts_dir: Directory where the log.md file is stored
        iteration: Iteration number
        postmortem_content: Content from postmortem agent
    """
    try:
        if not postmortem_content:
            print_status(
                f"No postmortem content to add for iteration {iteration}", "info"
            )
            return

        section_content = f"""### Iteration Postmortem

{postmortem_content}

"""

        _append_to_workflow_log(artifacts_dir, section_content)
        print_status(
            f"Added postmortem analysis for iteration {iteration} to workflow log",
            "success",
        )

    except Exception as e:
        print_status(
            f"Failed to add postmortem analysis for iteration {iteration} to log.md: {e}",
            "warning",
        )


def add_research_to_log(
    artifacts_dir: str,
    iteration: int,
    research_results: dict,
) -> None:
    """
    Add research findings section to the workflow log for the current iteration.
    This should be called immediately after research agents complete.

    Args:
        artifacts_dir: Directory where the log.md file is stored
        iteration: Iteration number
        research_results: Dictionary of research results from research agents
    """
    try:
        if not research_results:
            print_status(
                f"No research results to add for iteration {iteration}", "info"
            )
            return

        # Compile research content from results with extracted and normalized headers
        research_sections = []
        for focus, result in research_results.items():
            # First extract only the ### Research section
            extracted_content = _extract_research_section(result["content"])
            # Then normalize headers in the extracted research content
            normalized_content = _normalize_research_headers(extracted_content)
            research_sections.append(f"#### {result['title']}\n\n{normalized_content}")

        research_content = "\n\n".join(research_sections)
        section_content = f"""### Research Findings

{research_content}

"""

        _append_to_workflow_log(artifacts_dir, section_content)
        print_status(
            f"Added research findings for iteration {iteration} to workflow log",
            "success",
        )

    except Exception as e:
        print_status(
            f"Failed to add research findings for iteration {iteration} to log.md: {e}",
            "warning",
        )


def add_test_output_to_log(
    artifacts_dir: str,
    iteration: int,
    test_output: str = None,
    test_output_is_meaningful: bool = True,
    matched_iteration: int = None,
) -> None:
    """
    Add just the test output section to the workflow log and tests log for the current iteration.
    This should be called immediately after running tests.

    Args:
        artifacts_dir: Directory where the log.md and tests.md files are stored
        iteration: Iteration number
        test_output: Test output (only if meaningful change or first iteration)
        test_output_is_meaningful: Whether test output represents a meaningful change
        matched_iteration: The iteration number that this test output matches (when not meaningful)
    """
    try:
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        # Content for log.md (full workflow log)
        log_section_content = f"""
## Iteration {iteration} - {timestamp}

"""

        # Content for tests.md (only test outputs)
        tests_section_content = f"""
## Iteration {iteration} - {timestamp}

"""

        # Add test output section to both files
        if test_output_is_meaningful and test_output:
            test_output_section = f"""### Test Output

```
{test_output}
```

"""
            log_section_content += test_output_section
            tests_section_content += test_output_section
        elif not test_output_is_meaningful:
            if matched_iteration is not None:
                test_output_section = f"""### Test Output

Test output was the same as iteration {matched_iteration}.

"""
            else:
                test_output_section = """### Test Output

No meaningful change to test output.

"""
            log_section_content += test_output_section
            tests_section_content += test_output_section

        # Append to both files
        _append_to_workflow_log(artifacts_dir, log_section_content)
        _append_to_tests_log(artifacts_dir, tests_section_content)

        print_status(
            f"Added test output for iteration {iteration} to workflow and tests logs",
            "success",
        )

    except Exception as e:
        print_status(
            f"Failed to add test output for iteration {iteration} to log files: {e}",
            "warning",
        )


def add_iteration_section_to_log(
    artifacts_dir: str,
    iteration: int,
    planner_response: str | None = None,
) -> None:
    """
    Add planning content to the workflow log.
    Note: Test output, research, and postmortem should be added separately using respective functions.

    Args:
        artifacts_dir: Directory where the log.md file is stored
        iteration: Iteration number (used only for logging messages)
        planner_response: The planner agent's response
    """
    try:
        section_content = ""

        # Add planner response if provided
        if planner_response:
            section_content += f"""### Planner Agent Response

{planner_response}

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
    Finalize the log.md and tests.md files for a completed workflow run.

    Args:
        artifacts_dir: Directory where the log.md and tests.md files are stored
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

        # Finalize both log files
        _append_to_workflow_log(artifacts_dir, final_entry)
        _append_to_tests_log(artifacts_dir, final_entry)

        print_file_operation(
            "Finalized workflow log", _get_workflow_log_file(artifacts_dir), True
        )
        print_file_operation(
            "Finalized tests log", _get_tests_log_file(artifacts_dir), True
        )

    except Exception as e:
        print_status(f"Failed to finalize log files: {e}", "warning")

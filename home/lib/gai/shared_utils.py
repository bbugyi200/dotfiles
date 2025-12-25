import os
import random
import string
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from rich.console import Console
from rich_utils import print_command_execution, print_file_operation, print_status

# Type for change action prompt results
ChangeAction = Literal["accept", "commit", "reject", "purge"]

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


def _delete_proposal_entry(
    project_file: str, cl_name: str, base_num: int, letter: str
) -> bool:
    """Delete a proposal entry from a ChangeSpec's HISTORY.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name.
        base_num: The base number of the proposal (e.g., 2 for "2a").
        letter: The letter of the proposal (e.g., "a" for "2a").

    Returns:
        True if successful, False otherwise.
    """
    import tempfile

    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False

    # Find the ChangeSpec and its history section
    in_target_changespec = False
    new_lines: list[str] = []
    skip_until_next_entry = False
    proposal_pattern = f"({base_num}{letter})"

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            skip_until_next_entry = False
            new_lines.append(line)
            i += 1
            continue

        if in_target_changespec:
            stripped = line.strip()
            # Check if this is the proposal entry to delete
            if stripped.startswith(proposal_pattern):
                # Skip this entry and its metadata lines
                skip_until_next_entry = True
                i += 1
                continue
            # Check if we're still in metadata for skipped entry
            if skip_until_next_entry:
                if stripped.startswith("| "):
                    # Skip metadata line
                    i += 1
                    continue
                else:
                    # No longer in metadata
                    skip_until_next_entry = False

        new_lines.append(line)
        i += 1

    # Write back atomically
    project_dir = os.path.dirname(project_file)
    fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".gp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        os.replace(temp_path, project_file)
        return True
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        return False


def prompt_for_change_action(
    console: Console,
    target_dir: str,
    propose_mode: bool = True,  # Kept for API compatibility
    workflow_name: str | None = None,
    chat_path: str | None = None,
    shared_timestamp: str | None = None,
) -> tuple[ChangeAction, str | None] | None:
    """
    Prompt user for action on uncommitted changes.

    This function:
    1. Checks for uncommitted changes using `branch_local_changes`
    2. If no changes, returns None
    3. Creates a proposal from the changes (if on a branch)
    4. Prompts user with options: a/c/n/x (Enter = view diff)
    5. Returns the selected action and proposal ID (for accept/purge)

    Args:
        console: Rich Console for output
        target_dir: Directory to check for changes
        propose_mode: Deprecated parameter (always uses propose mode)
        workflow_name: Name of the workflow for the proposal note
        chat_path: Optional path to chat file for HISTORY entry
        shared_timestamp: Optional shared timestamp for synced chat/diff files

    Returns:
        ("accept", "<proposal_id>") - User chose 'a' to accept proposal
        ("commit", "<args>") - User chose 'c <args>'
        ("reject", "<proposal_id>") - User chose 'n' (proposal stays)
        ("purge", "<proposal_id>") - User chose 'x' (delete proposal)
        None - No changes detected
    """
    # Import here to avoid circular imports
    from history_utils import (
        add_proposed_history_entry,
        clean_workspace,
        save_diff,
    )

    # Check for uncommitted changes using branch_local_changes
    result = run_shell_command("branch_local_changes", capture_output=True)
    if not result.stdout.strip():
        return None  # No changes

    # Check if there's a branch to propose to
    branch_result = run_shell_command("branch_name", capture_output=True)
    branch_name = branch_result.stdout.strip() if branch_result.returncode == 0 else ""

    proposal_id: str | None = None

    # If we have a branch, create a proposal first
    if branch_name:
        # Get project info
        workspace_result = run_shell_command("workspace_name", capture_output=True)
        project = (
            workspace_result.stdout.strip()
            if workspace_result.returncode == 0
            else None
        )

        if project:
            project_file = os.path.expanduser(f"~/.gai/projects/{project}/{project}.gp")

            if os.path.isfile(project_file):
                # Build proposal note
                if workflow_name:
                    propose_note = f"[{workflow_name}]"
                else:
                    propose_note = "[agent]"

                # Save the diff
                diff_path = save_diff(
                    branch_name, target_dir=target_dir, timestamp=shared_timestamp
                )

                if diff_path:
                    # Create proposed HISTORY entry
                    success, entry_id = add_proposed_history_entry(
                        project_file=project_file,
                        cl_name=branch_name,
                        note=propose_note,
                        diff_path=diff_path,
                        chat_path=chat_path,
                    )
                    if success and entry_id:
                        proposal_id = entry_id
                        console.print(
                            f"[cyan]Created proposal ({proposal_id}): {propose_note}[/cyan]"
                        )
                        # Clean workspace after creating proposal
                        clean_workspace(target_dir)

    # Build prompt based on whether we created a proposal
    if proposal_id:
        prompt_text = (
            f"\n[cyan]a (accept {proposal_id}) | "
            "c <name> (commit) | n (skip) | x (purge):[/cyan] "
        )
    elif branch_name:
        # Fallback if proposal creation failed
        prompt_text = (
            f"\n[cyan]a <msg> (propose to {branch_name}) | "
            "c <name> (commit) | n (skip) | x (purge):[/cyan] "
        )
    else:
        prompt_text = "\n[cyan]c <name> (commit) | n (skip) | x (purge):[/cyan] "

    # Prompt loop
    while True:
        console.print(prompt_text, end="")
        user_input = input().strip()

        if user_input == "":
            # Show diff (either from workspace or from saved diff)
            console.print()
            if proposal_id:
                # Workspace was cleaned after creating proposal
                # Just inform user that proposal diff is saved
                try:
                    result = subprocess.run(
                        ["hg", "diff", "--color=always"],
                        cwd=target_dir,
                        capture_output=True,
                        text=True,
                    )
                    if result.stdout.strip():
                        print(result.stdout)
                    else:
                        console.print(
                            "[dim]Workspace is clean. Proposal diff saved.[/dim]"
                        )
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
            else:
                try:
                    subprocess.run(
                        ["hg", "diff", "--color=always"],
                        cwd=target_dir,
                        check=True,
                    )
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
            continue  # Prompt again

        if user_input == "a":
            if proposal_id:
                # Accept the proposal
                return ("accept", proposal_id)
            elif not branch_name:
                console.print(
                    "[red]Error: 'a' is not available - no branch found[/red]"
                )
                continue
            else:
                # Fallback to old behavior if proposal wasn't created
                console.print(
                    "[red]Error: 'a' requires a message (e.g., 'a fix typo')[/red]"
                )
                continue
        elif user_input.startswith("a "):
            if proposal_id:
                # Already have a proposal, just accept it (ignore extra text)
                return ("accept", proposal_id)
            elif not branch_name:
                console.print(
                    "[red]Error: 'a' is not available - no branch found[/red]"
                )
                continue
            else:
                # Proposal creation failed earlier, can't accept
                console.print(
                    "[red]Error: No proposal was created. Cannot accept.[/red]"
                )
                continue
        elif user_input.startswith("c "):
            # Extract args after "c "
            commit_args = user_input[2:].strip()
            if commit_args:
                return ("commit", commit_args)
            else:
                console.print(
                    "[red]Error: 'c' requires a CL name (e.g., 'c my_feature')[/red]"
                )
                continue
        elif user_input == "c":
            console.print(
                "[red]Error: 'c' requires a CL name (e.g., 'c my_feature')[/red]"
            )
            continue
        elif user_input == "n":
            return ("reject", proposal_id)
        elif user_input == "x":
            return ("purge", proposal_id)
        else:
            console.print(f"[red]Invalid option: {user_input}[/red]")


def execute_change_action(
    action: ChangeAction,
    action_args: str | None,
    console: Console,
    target_dir: str,
    workflow_tag: str | None = None,
    workflow_name: str | None = None,
    chat_path: str | None = None,
    shared_timestamp: str | None = None,
) -> bool:
    """
    Execute the action selected by prompt_for_change_action.

    Args:
        action: The action to execute ("accept", "amend", "commit", "reject",
            "purge", "propose")
        action_args: Arguments for the action (proposal_id for "accept"/"purge",
            message for "amend"/"propose", CL name for "commit")
        console: Rich Console for output
        target_dir: Directory where changes are located
        workflow_tag: Optional workflow tag for amend commit message
        workflow_name: Optional workflow name for amend commit message
        chat_path: Optional path to chat file for HISTORY entry
        shared_timestamp: Optional shared timestamp for synced chat/diff files

    Returns:
        True if action completed successfully, False otherwise
    """
    if action == "accept":
        # Accept a proposal: apply diff, amend, renumber
        if not action_args:
            console.print("[red]Error: accept requires a proposal ID[/red]")
            return False

        proposal_id = action_args

        # Import accept workflow functions
        from accept_workflow import (
            _find_proposal_entry,
            _get_changespec_from_file,
            _parse_proposal_id,
            _renumber_history_entries,
        )
        from history_utils import apply_diff_to_workspace

        # Parse proposal ID
        parsed = _parse_proposal_id(proposal_id)
        if not parsed:
            console.print(f"[red]Invalid proposal ID: {proposal_id}[/red]")
            return False
        base_num, letter = parsed

        # Get project and CL info
        workspace_result = run_shell_command("workspace_name", capture_output=True)
        project = (
            workspace_result.stdout.strip()
            if workspace_result.returncode == 0
            else None
        )
        if not project:
            console.print("[red]Failed to get project name[/red]")
            return False

        branch_result = run_shell_command("branch_name", capture_output=True)
        cl_name = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
        if not cl_name:
            console.print("[red]Failed to get branch name[/red]")
            return False

        project_file = os.path.expanduser(f"~/.gai/projects/{project}/{project}.gp")
        if not os.path.isfile(project_file):
            console.print(f"[red]Project file not found: {project_file}[/red]")
            return False

        # Get the proposal entry
        changespec = _get_changespec_from_file(project_file, cl_name)
        if not changespec:
            console.print(f"[red]ChangeSpec not found: {cl_name}[/red]")
            return False

        entry = _find_proposal_entry(changespec.history, base_num, letter)
        if not entry:
            console.print(f"[red]Proposal ({proposal_id}) not found[/red]")
            return False
        if not entry.diff:
            console.print(f"[red]Proposal ({proposal_id}) has no diff[/red]")
            return False

        # Apply the diff
        console.print(f"[cyan]Applying proposal ({proposal_id})...[/cyan]")
        success, error_msg = apply_diff_to_workspace(target_dir, entry.diff)
        if not success:
            console.print(f"[red]Failed to apply diff: {error_msg}[/red]")
            return False

        # Run bb_hg_amend with the proposal note
        console.print("[cyan]Amending commit...[/cyan]")
        try:
            result = subprocess.run(
                ["bb_hg_amend", entry.note],
                capture_output=True,
                text=True,
                cwd=target_dir,
            )
            if result.returncode != 0:
                console.print(f"[red]bb_hg_amend failed: {result.stderr}[/red]")
                return False
        except FileNotFoundError:
            console.print("[red]bb_hg_amend command not found[/red]")
            return False

        # Renumber history entries
        console.print("[cyan]Updating HISTORY...[/cyan]")
        if _renumber_history_entries(project_file, cl_name, [(base_num, letter)]):
            console.print("[green]HISTORY updated successfully.[/green]")
        else:
            console.print("[yellow]Warning: Failed to update HISTORY.[/yellow]")

        console.print(f"[green]Proposal ({proposal_id}) accepted![/green]")
        return True

    elif action == "commit":
        if not action_args:
            console.print("[red]Error: commit requires a CL name[/red]")
            return False

        # Run gai commit with the provided args
        console.print(f"[cyan]Running gai commit {action_args}...[/cyan]")
        try:
            cmd = ["gai", "commit", action_args]
            if chat_path:
                cmd.extend(["--chat", chat_path])
            if shared_timestamp:
                cmd.extend(["--timestamp", shared_timestamp])
            subprocess.run(
                cmd,
                cwd=target_dir,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]gai commit failed (exit code {e.returncode})[/red]")
            return False

        console.print("[green]Commit created successfully![/green]")
        return True

    elif action == "reject":
        console.print("[yellow]Changes rejected. Returning to view.[/yellow]")
        return False

    elif action == "purge":
        # Delete the proposal entry from HISTORY
        if not action_args:
            console.print("[yellow]No proposal to purge.[/yellow]")
            return False

        proposal_id = action_args

        # Import needed functions
        from accept_workflow import (
            _find_proposal_entry,
            _get_changespec_from_file,
            _parse_proposal_id,
        )

        # Parse proposal ID
        parsed = _parse_proposal_id(proposal_id)
        if not parsed:
            console.print(f"[red]Invalid proposal ID: {proposal_id}[/red]")
            return False
        base_num, letter = parsed

        # Get project and CL info
        workspace_result = run_shell_command("workspace_name", capture_output=True)
        project = (
            workspace_result.stdout.strip()
            if workspace_result.returncode == 0
            else None
        )
        if not project:
            console.print("[red]Failed to get project name[/red]")
            return False

        branch_result = run_shell_command("branch_name", capture_output=True)
        cl_name = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
        if not cl_name:
            console.print("[red]Failed to get branch name[/red]")
            return False

        project_file = os.path.expanduser(f"~/.gai/projects/{project}/{project}.gp")
        if not os.path.isfile(project_file):
            console.print(f"[red]Project file not found: {project_file}[/red]")
            return False

        # Get the proposal entry to find the diff path
        changespec = _get_changespec_from_file(project_file, cl_name)
        if changespec:
            entry = _find_proposal_entry(changespec.history, base_num, letter)
            if entry and entry.diff:
                # Delete the diff file
                try:
                    if os.path.isfile(entry.diff):
                        os.remove(entry.diff)
                        console.print(f"[dim]Deleted diff: {entry.diff}[/dim]")
                except OSError:
                    pass  # Ignore errors deleting diff

        # Delete the proposal entry from the project file
        console.print(f"[cyan]Deleting proposal ({proposal_id})...[/cyan]")
        success = _delete_proposal_entry(project_file, cl_name, base_num, letter)
        if success:
            console.print(f"[green]Proposal ({proposal_id}) deleted.[/green]")
        else:
            console.print("[yellow]Warning: Could not delete proposal entry.[/yellow]")

        return False  # Return False to indicate workflow didn't "succeed"

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        return False

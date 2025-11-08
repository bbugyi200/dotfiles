"""Workflow nodes for the work-projects workflow."""

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fix_tests_workflow.main import FixTestsWorkflow
from new_ez_feature_workflow.main import NewEzFeatureWorkflow
from new_failing_tests_workflow.main import NewFailingTestWorkflow
from new_tdd_feature_workflow.main import NewTddFeatureWorkflow
from rich.prompt import Prompt
from rich.text import Text
from rich_utils import console, print_status
from shared_utils import (
    create_artifacts_directory,
    generate_workflow_tag,
    initialize_gai_log,
    run_shell_command,
)
from status_state_machine import transition_changespec_status

from .state import WorkProjectState


def _get_statuses_for_filters(filters: list[str]) -> set[str]:
    """
    Convert filter categories to STATUS values.

    Args:
        filters: List of filter categories (blocked, unblocked, wip)

    Returns:
        Set of STATUS values to include. Empty set means include all.
    """
    if not filters:
        return set()  # Empty set means include all

    status_map = {
        "blocked": {"Pre-Mailed", "Failed to Fix Tests", "Failed to Create CL"},
        "unblocked": {"Not Started", "TDD CL Created"},
        "wip": {"In Progress", "Fixing Tests"},
    }

    result_statuses: set[str] = set()
    for filter_name in filters:
        result_statuses.update(status_map.get(filter_name, set()))

    return result_statuses


def _extract_bug_id(bug_value: str) -> str:
    """
    Extract bug ID from a BUG field value.

    Supports formats:
    - Plain ID: "12345" -> "12345"
    - URL format: "http://b/12345" -> "12345"
    - URL format: "https://b/12345" -> "12345"

    Args:
        bug_value: Raw BUG field value

    Returns:
        Extracted bug ID
    """
    bug_value = bug_value.strip()

    # Handle URL format: http://b/12345 or https://b/12345
    if bug_value.startswith("http://b/") or bug_value.startswith("https://b/"):
        prefix = "https://b/" if bug_value.startswith("https://") else "http://b/"
        return bug_value[len(prefix) :]

    # Plain ID format
    return bug_value


def _extract_cl_id(cl_value: str) -> str:
    """
    Extract CL ID from a CL field value.

    Supports formats:
    - Plain ID: "12345" -> "12345"
    - Legacy format: "cl/12345" -> "12345"
    - URL format: "http://cl/12345" -> "12345"
    - URL format: "https://cl/12345" -> "12345"

    Args:
        cl_value: Raw CL field value

    Returns:
        Extracted CL ID
    """
    cl_value = cl_value.strip()

    # Handle URL format: http://cl/12345 or https://cl/12345
    if cl_value.startswith("http://cl/") or cl_value.startswith("https://cl/"):
        prefix = "https://cl/" if cl_value.startswith("https://") else "http://cl/"
        return cl_value[len(prefix) :]

    # Handle legacy format: cl/12345
    if cl_value.startswith("cl/"):
        return cl_value[3:]

    # Plain ID format
    return cl_value


def _is_in_tmux() -> bool:
    """
    Check if the current session is running inside tmux.

    Returns:
        True if running in a tmux session, False otherwise
    """
    return os.environ.get("TMUX") is not None


def _has_test_output(project_file: str, cs: dict[str, str]) -> bool:
    """
    Check if test output exists for a ChangeSpec.

    Args:
        project_file: Path to the ProjectSpec file
        cs: ChangeSpec dictionary

    Returns:
        True if test output file exists, False otherwise
    """
    cs_name = cs.get("NAME", "").strip()
    if not cs_name:
        return False

    test_output_file = _get_test_output_file_path(project_file, cs_name)
    return os.path.exists(test_output_file)


def _view_test_output(project_file: str, cs: dict[str, str]) -> None:
    """
    View the test output for a ChangeSpec using less.

    Args:
        project_file: Path to the ProjectSpec file
        cs: ChangeSpec dictionary
    """
    cs_name = cs.get("NAME", "").strip()
    if not cs_name:
        print_status("No NAME available for this ChangeSpec", "warning")
        return

    test_output_file = _get_test_output_file_path(project_file, cs_name)
    if not os.path.exists(test_output_file):
        print_status(f"No test output found for {cs_name}", "warning")
        return

    print_status(f"Viewing test output for {cs_name}...", "progress")

    # Use less to view the test output
    try:
        subprocess.run(["less", test_output_file], check=False)
    except Exception as e:
        print_status(f"Error viewing test output: {e}", "error")


def _open_tmux_window_for_cl(cs: dict[str, str], project_dir: str) -> None:
    """
    Open a new tmux window and checkout the CL.

    Args:
        cs: ChangeSpec dictionary
        project_dir: Path to the project directory
    """
    cs_name = cs.get("NAME", "").strip()
    if not cs_name:
        print_status("No NAME available for this ChangeSpec", "warning")
        return

    cl_value = cs.get("CL", "").strip()
    if not cl_value or cl_value.lower() == "none":
        print_status("No CL available for this ChangeSpec", "warning")
        return

    # Extract CL ID from the CL field for display purposes
    cl_id = _extract_cl_id(cl_value)

    print_status(f"Opening new tmux window for {cs_name} (CL#{cl_id})...", "progress")

    # Build the command to run in the new tmux window
    # 1. cd to project directory
    # 2. run hg_update to checkout the CL
    # 3. start a shell
    commands = [
        f"cd {project_dir}",
        f"hg_update {cs_name}",
        "$SHELL",
    ]
    shell_command = " && ".join(commands)

    # Create a new tmux window with the ChangeSpec NAME
    try:
        subprocess.run(
            ["tmux", "new-window", "-n", cs_name, shell_command],
            check=True,
        )
        print_status(f"Opened tmux window '{cs_name}'", "success")
    except subprocess.CalledProcessError as e:
        print_status(f"Failed to create tmux window: {e}", "error")
    except Exception as e:
        print_status(f"Error creating tmux window: {e}", "error")


def _view_cl_diff(cs: dict[str, str]) -> None:
    """
    View the CL diff using hg_update and branch_diff.

    Args:
        cs: ChangeSpec dictionary
    """
    cs_name = cs.get("NAME", "").strip()
    if not cs_name:
        print_status("No NAME available for this ChangeSpec", "warning")
        return

    cl_value = cs.get("CL", "").strip()
    if not cl_value or cl_value.lower() == "none":
        print_status("No CL available for this ChangeSpec", "warning")
        return

    # Extract CL ID from the CL field for display purposes
    cl_id = _extract_cl_id(cl_value)

    print_status(f"Checking out CL {cs_name} (CL#{cl_id})...", "progress")

    # Run hg_update to checkout the CL using its NAME
    result = run_shell_command(f"hg_update {cs_name}", capture_output=True)
    if result.returncode != 0:
        print_status(f"Failed to checkout CL {cs_name}: {result.stderr}", "error")
        return

    print_status("Generating diff...", "progress")

    # Run branch_diff and pipe to less
    try:
        subprocess.run(
            "branch_diff --color=always | less -R",
            shell=True,
            check=False,
        )
    except Exception as e:
        print_status(f"Error viewing diff: {e}", "error")


def _prompt_status_change_for_work(current_status: str) -> str | None:
    """
    Prompt the user to select a new status for the ChangeSpec.

    Args:
        current_status: Current STATUS value

    Returns:
        New status value, or None to cancel
    """
    # All valid STATUS values
    valid_statuses = [
        "Not Started",
        "In Progress",
        "Failed to Create CL",
        "TDD CL Created",
        "Fixing Tests",
        "Failed to Fix Tests",
        "Pre-Mailed",
        "Mailed",
        "Submitted",
    ]

    # Get all valid statuses except the current one
    available_statuses = [s for s in valid_statuses if s != current_status]

    console.print("\n[bold]Select new STATUS:[/bold]")
    for i, status in enumerate(available_statuses, 1):
        console.print(f"  {i}. {status}")
    console.print("  c. Cancel")

    choice = Prompt.ask(
        "\nSelect an option",
        choices=[str(i) for i in range(1, len(available_statuses) + 1)] + ["c"],
        default="c",
    )

    if choice == "c":
        return None

    # Convert choice to status
    idx = int(choice) - 1
    return available_statuses[idx]


def _prompt_user_action_for_work(
    project_file: str,
    cs: dict[str, str],
    project_dir: str,
    workflow_name: str,
    current_index: int = 0,
    total_count: int = 0,
    can_go_prev: bool = False,
) -> tuple[str, str | None]:
    """
    Prompt the user for an action before starting work on the ChangeSpec.

    Args:
        project_file: Path to the ProjectSpec file
        cs: ChangeSpec dictionary
        project_dir: Path to the project directory
        workflow_name: Name of the workflow that will be run
        current_index: Current position in the list (1-based)
        total_count: Total number of eligible ChangeSpecs
        can_go_prev: Whether the user can go to the previous ChangeSpec

    Returns:
        Tuple of (action, new_status) where action is one of:
        - "run": Run workflow on this ChangeSpec
        - "skip": Skip this ChangeSpec
        - "update": Update STATUS to new_status value
        - "quit": Quit processing
        - "prev": Go to previous ChangeSpec
    """
    # Build list of available options
    options = []
    option_descriptions = []

    options.append("r")
    option_descriptions.append(f"  r. Run {workflow_name} on this ChangeSpec")

    options.append("s")
    option_descriptions.append("  s. Change STATUS")

    # Check if CL diff is available
    cl_value = cs.get("CL", "").strip()
    has_cl = cl_value and cl_value.lower() != "none"
    if has_cl:
        options.append("d")
        option_descriptions.append("  d. View CL diff")

    # Check if tmux window option should be shown
    if has_cl and _is_in_tmux():
        options.append("w")
        option_descriptions.append("  w. Open CL in new tmux window")

    # Check if test output is available
    if _has_test_output(project_file, cs):
        options.append("t")
        option_descriptions.append("  t. View test output")

    # Add prev option if available
    if can_go_prev:
        options.append("p")
        option_descriptions.append("  p. Previous ChangeSpec")

    # Add next option only if there are more ChangeSpecs to process
    is_last_changespec = current_index > 0 and current_index == total_count
    if not is_last_changespec:
        options.append("n")
        option_descriptions.append("  n. Next (skip this ChangeSpec)")

    options.append("q")
    option_descriptions.append("  q. Quit (stop processing)")

    # Show current position if available
    position_text = ""
    if current_index > 0 and total_count > 0:
        position_text = f" ({current_index}/{total_count})"

    console.print(f"\n[bold]Available options{position_text}:[/bold]")
    for desc in option_descriptions:
        console.print(desc)

    # Default to "n" if available, otherwise "q"
    default_option = "n" if not is_last_changespec else "q"

    choice = Prompt.ask(
        "\nSelect an option",
        choices=options,
        default=default_option,
    )

    if choice == "r":
        return ("run", None)
    elif choice == "n":
        return ("skip", None)
    elif choice == "q":
        return ("quit", None)
    elif choice == "p":
        return ("prev", None)
    elif choice == "s":
        current_status = cs.get("STATUS", "").strip()
        new_status = _prompt_status_change_for_work(current_status)
        if new_status:
            return ("update", new_status)
        else:
            # User cancelled, prompt again
            return _prompt_user_action_for_work(
                project_file,
                cs,
                project_dir,
                workflow_name,
                current_index,
                total_count,
                can_go_prev,
            )
    elif choice == "d":
        _view_cl_diff(cs)
        # After viewing diff, prompt again
        return _prompt_user_action_for_work(
            project_file,
            cs,
            project_dir,
            workflow_name,
            current_index,
            total_count,
            can_go_prev,
        )
    elif choice == "w":
        _open_tmux_window_for_cl(cs, project_dir)
        # After opening tmux window, prompt again
        return _prompt_user_action_for_work(
            project_file,
            cs,
            project_dir,
            workflow_name,
            current_index,
            total_count,
            can_go_prev,
        )
    elif choice == "t":
        _view_test_output(project_file, cs)
        # After viewing test output, prompt again
        return _prompt_user_action_for_work(
            project_file,
            cs,
            project_dir,
            workflow_name,
            current_index,
            total_count,
            can_go_prev,
        )

    # Should never get here, but default to skip
    return ("skip", None)


def initialize_work_project_workflow(state: WorkProjectState) -> WorkProjectState:
    """
    Initialize the work-projects workflow.

    Reads and parses the ProjectSpec file.
    """
    project_file = state["project_file"]

    # Validate project file exists
    if not os.path.isfile(project_file):
        return {
            **state,
            "failure_reason": f"Project file '{project_file}' does not exist",
        }

    # Extract project name from filename
    project_name = Path(project_file).stem
    state["project_name"] = project_name

    # Read and parse the ProjectSpec file
    try:
        with open(project_file) as f:
            content = f.read()

        bug_id, changespecs = _parse_project_spec(content)
        if not bug_id:
            return {
                **state,
                "failure_reason": "No BUG field found in project file",
            }
        if not changespecs:
            return {
                **state,
                "failure_reason": "No ChangeSpecs found in project file",
            }

        state["bug_id"] = bug_id
        state["changespecs"] = changespecs

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error reading project file: {e}",
        }

    return state


def _count_eligible_changespecs(
    changespecs: list[dict[str, str]],
    attempted_changespecs: list[str],
    include_filters: list[str],
) -> int:
    """
    Count the number of eligible ChangeSpecs.

    When filters are specified, counts ALL ChangeSpecs matching those filters.
    When no filters are specified, uses the AI workflow priority logic.

    Args:
        changespecs: List of all ChangeSpecs
        attempted_changespecs: List of ChangeSpec names already attempted
        include_filters: List of status categories to include

    Returns:
        Total number of eligible ChangeSpecs
    """
    allowed_statuses = _get_statuses_for_filters(include_filters)
    changespec_map = {cs.get("NAME", ""): cs for cs in changespecs if cs.get("NAME")}
    count = 0

    for cs in changespecs:
        name = cs.get("NAME", "")
        status = cs.get("STATUS", "").strip()

        # Skip if no NAME field
        if not name:
            continue

        # Skip if already attempted
        if name in attempted_changespecs:
            continue

        # If filters are specified, count ALL ChangeSpecs matching the filter
        if allowed_statuses:
            if status in allowed_statuses:
                count += 1
        else:
            # No filters - use AI workflow eligibility logic
            if status == "TDD CL Created":
                count += 1
            elif status == "Not Started":
                parent = cs.get("PARENT", "").strip()
                # Check if no parent or parent is completed
                if parent == "None":
                    count += 1
                elif parent in changespec_map:
                    parent_status = changespec_map[parent].get("STATUS", "").strip()
                    if parent_status in ["Pre-Mailed", "Mailed", "Submitted"]:
                        count += 1

    return count


def select_next_changespec(state: WorkProjectState) -> WorkProjectState:
    """
    Select the next eligible ChangeSpec to work on.

    Priority order:
    1. FIRST ChangeSpec with status "TDD CL Created" (ready for fix-tests)
    2. FIRST "Not Started" ChangeSpec that either:
       - Does NOT have any parent (PARENT == "None"), OR
       - Has a parent ChangeSpec that is "Pre-Mailed", "Mailed", or "Submitted"

    Skips ChangeSpecs that have already been attempted in this workflow run.
    Also creates artifacts directory and extracts ChangeSpec fields.

    If include_filters is specified, only ChangeSpecs matching the filter will be considered.

    Handles navigation:
    - If user_requested_prev is True, goes back to the previous ChangeSpec in history
    - Otherwise, selects the next ChangeSpec according to priority rules
    """
    # Re-read the project file to get current STATUS values
    # (they may have been updated by previous workflow iterations)
    project_file = state["project_file"]
    try:
        with open(project_file) as f:
            content = f.read()
        _, changespecs = _parse_project_spec(content)
        # Update the state with fresh changespecs
        state["changespecs"] = changespecs
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error re-reading project file in select_next: {e}",
        }

    changespecs = state["changespecs"]
    attempted_changespecs = state.get("attempted_changespecs", [])
    include_filters = state.get("include_filters", [])

    # Get navigation state
    user_requested_prev = state.get("user_requested_prev", False)
    changespec_history = state.get("changespec_history", [])
    current_changespec_index = state.get("current_changespec_index", -1)

    # Check if user requested to go to previous ChangeSpec
    selected_cs = None
    if user_requested_prev and changespec_history and current_changespec_index > 0:
        # Go back to the previous ChangeSpec
        current_changespec_index -= 1
        selected_cs = changespec_history[current_changespec_index]
        cs_name = selected_cs.get("NAME", "")
        print_status(
            f"Going back to previous ChangeSpec: {cs_name} (position {current_changespec_index + 1})",
            "success",
        )

        # Check if this ChangeSpec is from a different project file
        prev_project_file = selected_cs.get("_project_file")
        if prev_project_file and prev_project_file != project_file:
            # Update the project_file and re-read the changespecs and metadata from that file
            from pathlib import Path

            project_file = prev_project_file
            state["project_file"] = project_file

            # Update project_name (derived from filename)
            project_path = Path(project_file)
            project_name = project_path.stem
            state["project_name"] = project_name

            try:
                with open(project_file) as f:
                    content = f.read()
                bug_id, changespecs_from_file = _parse_project_spec(content)
                state["changespecs"] = changespecs_from_file
                state["bug_id"] = bug_id or ""
                changespecs = changespecs_from_file
            except Exception as e:
                return {
                    **state,
                    "failure_reason": f"Error reading project file {project_file} during prev navigation: {e}",
                }

        # Clear the prev flag
        state["user_requested_prev"] = False
        state["user_requested_prev_failed"] = False  # Clear failed flag on success
        state["current_changespec_index"] = current_changespec_index

        # Skip to the artifacts creation section
        # (We'll handle this after the selection logic)
    elif user_requested_prev:
        # User requested prev but can't go back (at beginning of global history)
        changespec_history_check = state.get("changespec_history", [])
        if not changespec_history_check or current_changespec_index <= 0:
            print_status(
                "Cannot go back - already at the first ChangeSpec.",
                "warning",
            )
        state["user_requested_prev"] = False
        state["user_requested_prev_failed"] = True  # Mark that prev failed
        # Fall through to select next ChangeSpec normally

    # Check if we should move forward in history instead of selecting a new ChangeSpec
    # This happens when we're in the middle of history (not at the end) after going back with "p"
    # But NOT if the user's prev attempt just failed
    if (
        not selected_cs
        and changespec_history
        and current_changespec_index >= 0
        and current_changespec_index < len(changespec_history) - 1
        and not state.get("user_requested_prev_failed", False)
    ):
        # We're in the middle of history - move forward to the next item in history
        current_changespec_index += 1
        selected_cs = changespec_history[current_changespec_index]
        cs_name = selected_cs.get("NAME", "")
        print_status(
            f"Moving forward in history to: {cs_name} (position {current_changespec_index + 1})",
            "success",
        )

        # Check if this ChangeSpec is from a different project file
        next_project_file = selected_cs.get("_project_file")
        if next_project_file and next_project_file != project_file:
            # Update the project_file and re-read the changespecs and metadata from that file
            from pathlib import Path

            project_file = next_project_file
            state["project_file"] = project_file

            # Update project_name (derived from filename)
            project_path = Path(project_file)
            project_name = project_path.stem
            state["project_name"] = project_name

            try:
                with open(project_file) as f:
                    content = f.read()
                bug_id, changespecs_from_file = _parse_project_spec(content)
                state["changespecs"] = changespecs_from_file
                state["bug_id"] = bug_id or ""
                changespecs = changespecs_from_file
            except Exception as e:
                return {
                    **state,
                    "failure_reason": f"Error reading project file {project_file} during forward navigation: {e}",
                }

        # Update the index in state
        state["current_changespec_index"] = current_changespec_index

    # Get the set of statuses to include based on filters
    allowed_statuses = _get_statuses_for_filters(include_filters)

    # Build a map of NAME -> ChangeSpec for easy lookup
    changespec_map = {cs.get("NAME", ""): cs for cs in changespecs if cs.get("NAME")}

    # Only select a new ChangeSpec if we didn't retrieve one from history
    if not selected_cs:
        # If filters are specified, select ANY ChangeSpec matching the filter
        # (allows user to review blocked/wip items even if AI can't process them)
        if allowed_statuses:
            for cs in changespecs:
                name = cs.get("NAME", "")
                status = cs.get("STATUS", "").strip()

                # Skip if no NAME field
                if not name:
                    continue

                # Skip if already attempted
                if name in attempted_changespecs:
                    continue

                # Select if status matches filter
                if status in allowed_statuses:
                    selected_cs = cs
                    print_status(
                        f"Selected ChangeSpec: {name} (status: {status})",
                        "success",
                    )
                    # Don't run hg_update for non-processable statuses
                    # The user will manually review these
                    break
            # If filters were specified but no matching ChangeSpec found,
            # don't fall through to unfiltered selection - we're done
        # No filters specified - use AI workflow priority logic
        elif not selected_cs:
            for cs in changespecs:
                name = cs.get("NAME", "")
                status = cs.get("STATUS", "").strip()

                # Skip if no NAME field
                if not name:
                    continue

                # Skip if already attempted
                if name in attempted_changespecs:
                    continue

                if status == "TDD CL Created":
                    selected_cs = cs
                    print_status(
                        f"Selected ChangeSpec: {name} (TDD CL Created - ready for fix-tests)",
                        "success",
                    )

                # Update to this changelist since it already exists
                try:
                    result = run_shell_command(f"hg_update {name}", capture_output=True)
                    if result.returncode == 0:
                        pass
                    else:
                        error_msg = f"hg_update to {name} failed with exit code {result.returncode}"
                        if result.stderr:
                            error_msg += f": {result.stderr}"
                        return {
                            **state,
                            "failure_reason": error_msg,
                        }
                except Exception as e:
                    return {
                        **state,
                        "failure_reason": f"Failed to run hg_update to {name}: {e}",
                    }

                    break

            # PRIORITY 2: If no "TDD CL Created" found, find "Not Started" ChangeSpec
            if not selected_cs:
                for cs in changespecs:
                    name = cs.get("NAME", "")
                    status = cs.get("STATUS", "").strip()
                    parent = cs.get("PARENT", "").strip()

                    # Skip if no NAME field
                    if not name:
                        print_status(
                            "Skipping ChangeSpec with no NAME field", "warning"
                        )
                        continue

                    # Skip if already attempted
                    if name in attempted_changespecs:
                        continue

                    # Skip if not "Not Started"
                    if status != "Not Started":
                        continue

                    # Check if no parent or parent is completed
                    if parent == "None":
                        # No parent - eligible
                        selected_cs = cs
                        print_status(
                            f"Selected ChangeSpec: {name} (no parent)", "success"
                        )

                        # Update to p4head since this is the first CL in the chain
                        try:
                            result = run_shell_command(
                                "hg_update p4head", capture_output=True
                            )
                            if result.returncode == 0:
                                pass
                            else:
                                error_msg = f"hg_update to p4head failed with exit code {result.returncode}"
                                if result.stderr:
                                    error_msg += f": {result.stderr}"
                                return {
                                    **state,
                                    "failure_reason": error_msg,
                                }
                        except Exception as e:
                            return {
                                **state,
                                "failure_reason": f"Failed to run hg_update to p4head: {e}",
                            }

                        break

                    # Check if parent is in a completed state
                    if parent in changespec_map:
                        parent_status = changespec_map[parent].get("STATUS", "").strip()
                        if parent_status in ["Pre-Mailed", "Mailed", "Submitted"]:
                            selected_cs = cs
                            print_status(
                                f"Selected ChangeSpec: {name} (parent {parent} is {parent_status})",
                                "success",
                            )

                            # Update to the parent changelist
                            try:
                                result = run_shell_command(
                                    f"hg_update {parent}", capture_output=True
                                )
                                if result.returncode == 0:
                                    pass
                                else:
                                    error_msg = f"hg_update to parent {parent} failed with exit code {result.returncode}"
                                    if result.stderr:
                                        error_msg += f": {result.stderr}"
                                    return {
                                        **state,
                                        "failure_reason": error_msg,
                                    }
                            except Exception as e:
                                return {
                                    **state,
                                    "failure_reason": f"Failed to run hg_update to parent {parent}: {e}",
                                }

                            break

    if not selected_cs:
        # No eligible ChangeSpec found
        return {
            **state,
            "failure_reason": "No eligible ChangeSpec found (all are either completed, blocked by incomplete parents, or already attempted)",
        }

    # Extract ChangeSpec fields
    cl_name = selected_cs.get("NAME", "")
    cl_description = selected_cs.get("DESCRIPTION", "")

    # Generate workflow tag and create artifacts directory
    workflow_tag = generate_workflow_tag()
    artifacts_dir = create_artifacts_directory()

    # Initialize gai.md log
    initialize_gai_log(artifacts_dir, "work-projects", workflow_tag)

    # Run clsurf command if project_name is available
    project_name = state["project_name"]
    clsurf_output_file = None
    if project_name:
        clsurf_cmd = f"clsurf 'a:me -tag:archive is:submitted {project_name}'"
        try:
            result = run_shell_command(clsurf_cmd, capture_output=True)
            clsurf_output_file = os.path.join(artifacts_dir, "clsurf_output.txt")
            with open(clsurf_output_file, "w") as f:
                f.write(f"# Command: {clsurf_cmd}\n")
                f.write(f"# Return code: {result.returncode}\n\n")
                f.write(result.stdout)
                if result.stderr:
                    f.write(f"\n# STDERR:\n{result.stderr}")
        except Exception as e:
            print_status(f"Warning: Failed to run clsurf command: {e}", "warning")

    # Update history and calculate total count
    # Check if this ChangeSpec is already in history (by NAME)
    cs_name = selected_cs.get("NAME", "")

    # First, check if we already have this ChangeSpec in history
    existing_index = -1
    for i, hist_cs in enumerate(changespec_history):
        if hist_cs.get("NAME") == cs_name:
            existing_index = i
            break

    if existing_index >= 0:
        # ChangeSpec already in history - just update the index to point to it
        current_changespec_index = existing_index
    elif current_changespec_index == -1 or current_changespec_index >= len(
        changespec_history
    ):
        # Adding a new ChangeSpec to the history
        # Store the project_file with the ChangeSpec for cross-file navigation
        cs_with_file = {**selected_cs, "_project_file": project_file}
        changespec_history = changespec_history + [cs_with_file]
        current_changespec_index = len(changespec_history) - 1
    # If we went back in history (and it's not a duplicate), keep the history as is

    # Calculate total eligible ChangeSpecs (excluding already attempted ones)
    total_eligible = _count_eligible_changespecs(
        changespecs, attempted_changespecs, include_filters
    )

    return {
        **state,
        "selected_changespec": selected_cs,
        "cl_name": cl_name,
        "cl_description": cl_description,
        "artifacts_dir": artifacts_dir,
        "workflow_tag": workflow_tag,
        "clsurf_output_file": clsurf_output_file,
        "messages": [],
        "changespec_history": changespec_history,
        "current_changespec_index": current_changespec_index,
        "total_eligible_changespecs": total_eligible,
        "user_requested_prev_failed": False,  # Clear flag when selecting new CS
    }


def invoke_create_cl(state: WorkProjectState) -> WorkProjectState:
    """
    Invoke the appropriate workflow based on ChangeSpec status and TEST TARGETS.

    Always prints the ChangeSpec details before starting work.

    For "Not Started" ChangeSpecs:
    - If TEST TARGETS is "None": Run new-change workflow (no tests required)
    - If TEST TARGETS has targets: Run fix-tests workflow with those targets
    - If TEST TARGETS is omitted: Use TDD workflow (new-failing-test -> fix-tests)

    For "TDD CL Created" ChangeSpecs:
    1. Load test output from persistent storage
    2. Implement feature to make tests pass (fix-tests)
    3. Update status to "Pre-Mailed" on success

    If yolo is False, prompts for confirmation before starting work.
    """
    selected_cs = state["selected_changespec"]
    if not selected_cs:
        return {
            **state,
            "failure_reason": "No ChangeSpec selected to invoke workflows",
        }

    yolo = state.get("yolo", False)
    cs_name = selected_cs.get("NAME", "UNKNOWN")
    cs_status = selected_cs.get("STATUS", "").strip()
    test_targets = selected_cs.get("TEST TARGETS", "").strip()

    # ALWAYS print the ChangeSpec before starting work
    from rich.panel import Panel
    from rich_utils import console

    # Format the ChangeSpec with colors
    changespec_colored = _format_changespec_with_colors(selected_cs)

    console.print(
        Panel(
            changespec_colored,
            title=f"ChangeSpec: {cs_name}",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # Determine which workflow will be run based on status and test targets
    workflow_name = ""
    if cs_status == "TDD CL Created":
        workflow_name = "fix-tests"
    elif cs_status == "Not Started":
        if test_targets and test_targets != "None":
            workflow_name = "new-failing-test"
        else:
            workflow_name = "new-ez-feature"
    elif cs_status == "In Progress":
        if test_targets and test_targets != "None":
            workflow_name = "fix-tests-with-initial-capture"
        else:
            workflow_name = "new-ez-feature"
    else:
        workflow_name = "unknown"

    # Prompt for confirmation unless yolo mode is enabled
    if not yolo:
        # Get project directory for tmux window option
        project_name = state["project_name"]
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR", "")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE", "")
        project_dir = os.path.join(goog_cloud_dir, project_name, goog_src_dir_base)
        project_file = state["project_file"]

        # Calculate global position using the global history index
        # Since we're using global history across all workflows, the index IS the global position
        current_changespec_index = state.get("current_changespec_index", -1)
        global_total = state.get("global_total_eligible", 0)

        # Position is simply the index + 1 (convert 0-based to 1-based)
        # The global history tracks ALL ChangeSpecs across all files
        if current_changespec_index < 0:
            # Should never happen (select_next always sets it), but safety check
            current_index = 1
        else:
            # Normal case: index is 0-based, position is 1-based
            current_index = current_changespec_index + 1

        total_count = global_total

        # VALIDATION: Check for invalid position jumps
        last_shown_position = state.get("last_shown_position", 0)

        if last_shown_position > 0:  # Not the first ChangeSpec
            # Detect direction by comparing positions
            # (Can't rely on user_requested_prev flag - it may have been cleared)
            went_backward = current_index < last_shown_position
            went_forward = current_index > last_shown_position

            # Valid navigation: can only move by 1 position or stay in place
            valid_positions = {
                last_shown_position - 1,  # Backward by 1
                last_shown_position,  # Stay
                last_shown_position + 1,  # Forward by 1
            }

            if current_index not in valid_positions:
                error_msg = (
                    f"VALIDATION FAILED: Invalid position jump detected!\n"
                    f"  Last shown position: {last_shown_position}\n"
                    f"  Current position: {current_index}\n"
                    f"  Jump size: {current_index - last_shown_position}\n"
                    f"  Direction: {'backward' if went_backward else 'forward' if went_forward else 'same'}\n"
                    f"  Valid positions: {sorted(valid_positions)}\n"
                    f"  current_changespec_index: {current_changespec_index}\n"
                    f"  changespec_history length: {len(state.get('changespec_history', []))}"
                )
                print_status(error_msg, "error")
                # Fail loudly by raising an exception
                raise ValueError(error_msg)

        # Update last shown position for next validation
        state["last_shown_position"] = current_index

        # Can go prev if we're not at the first ChangeSpec in global history
        can_go_prev = current_changespec_index > 0

        # Use the interactive prompt
        action, new_status = _prompt_user_action_for_work(
            project_file,
            selected_cs,
            project_dir,
            workflow_name,
            current_index,
            total_count,
            can_go_prev,
        )

        if action == "skip":
            print_status(f"Skipping ChangeSpec: {cs_name}", "info")
            state["success"] = False
            state["failure_reason"] = "User skipped ChangeSpec"
            # When user explicitly skips, move past current position in history
            # so we select a NEW changespec, not auto-forward through history
            state["current_changespec_index"] = len(state.get("changespec_history", []))
            return state
        elif action == "quit":
            state["success"] = False
            state["failure_reason"] = "User requested quit"
            state["user_requested_quit"] = True
            return state
        elif action == "prev":
            state["success"] = False
            state["failure_reason"] = "User requested previous ChangeSpec"
            state["user_requested_prev"] = True
            return state
        elif action == "update" and new_status:
            # Update the STATUS
            try:
                from status_state_machine import transition_changespec_status

                success, old_status, error = transition_changespec_status(
                    project_file, cs_name, new_status, validate=False
                )
                if success:
                    print_status(
                        f"Updated {cs_name} STATUS: {cs_status} → {new_status}",
                        "success",
                    )
                    # After updating status, mark as skipped to let workflow continue
                    state["success"] = False
                    state["failure_reason"] = "User manually updated STATUS"
                    return state
                else:
                    print_status(f"Error updating {cs_name} STATUS: {error}", "error")
                    # After failed update, skip this ChangeSpec
                    state["success"] = False
                    state["failure_reason"] = "Failed to update STATUS"
                    return state
            except Exception as e:
                print_status(f"Error updating STATUS: {e}", "error")
                state["success"] = False
                state["failure_reason"] = f"Error updating STATUS: {e}"
                return state
        # else action == "run", continue with workflow

    # Branch based on ChangeSpec status and TEST TARGETS
    if cs_status == "TDD CL Created":
        # CASE 1: TDD CL already created, run fix-tests workflow
        return _run_fix_tests_for_tdd_cl(state)
    elif cs_status == "Not Started":
        # Check TEST TARGETS to determine which workflow to use
        if test_targets == "None":
            # CASE 2A: No tests required, run new-change workflow
            return _run_new_change(state)
        elif test_targets:
            # CASE 2B: Specific test targets provided, run fix-tests directly
            return _run_fix_tests_with_targets(state)
        else:
            # CASE 2C: No TEST TARGETS field, use default TDD workflow
            return _run_create_test_cl(state)
    else:
        # Non-processable status (e.g., Pre-Mailed, Failed to Fix Tests, etc.)
        # These are shown for user review when using filters like `-i blocked`
        print_status(
            f"ChangeSpec '{cs_name}' has status '{cs_status}' which requires manual action. "
            "Use the prompt options to skip or update status.",
            "info",
        )
        return {
            **state,
            "success": False,
            "failure_reason": f"ChangeSpec status '{cs_status}' requires manual review (not auto-processable)",
        }


def _run_create_test_cl(state: WorkProjectState) -> WorkProjectState:
    """
    Run new-failing-test workflow for a "Not Started" ChangeSpec.

    Updates status to "In Progress", creates test CL, saves test output,
    and updates status to "TDD CL Created".
    """
    selected_cs = state["selected_changespec"]
    if not selected_cs:
        return {
            **state,
            "failure_reason": "No ChangeSpec selected",
        }

    cs_name = selected_cs.get("NAME", "UNKNOWN")
    project_file = state["project_file"]
    project_name = state["project_name"]
    design_docs_dir = state["design_docs_dir"]
    changespec_text = _format_changespec(selected_cs)

    # Update the ChangeSpec STATUS to "In Progress" in the project file
    print_status(f"Updating STATUS to 'In Progress' for {cs_name}...", "progress")
    success, old_status, error = transition_changespec_status(
        project_file, cs_name, "In Progress", validate=True
    )
    if not success:
        return {
            **state,
            "failure_reason": f"Error updating STATUS: {error}",
        }

    # Mark that we've updated the status so we can revert on interrupt
    state["status_updated_to_in_progress"] = True

    # Update the workflow instance's current state for interrupt handling
    workflow_instance = state.get("workflow_instance")
    if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
        workflow_instance._update_current_state(state)

    # Track this intermediate state for cleanup
    if workflow_instance and hasattr(workflow_instance, "_track_intermediate_state"):
        workflow_instance._track_intermediate_state(
            project_file, cs_name, "In Progress", tdd_cl_created=False
        )

    # Create test CL with failing tests
    try:
        # Create and run the new-failing-test workflow
        # Note: new-failing-test will run its own research agents
        new_failing_test_workflow = NewFailingTestWorkflow(
            project_name=project_name,
            design_docs_dir=design_docs_dir,
            changespec_text=changespec_text,
            research_file=None,
        )

        test_workflow_success = new_failing_test_workflow.run()

        if not test_workflow_success:
            # Get failure reason from final state if available
            failure_reason = "new-failing-test workflow failed"
            if new_failing_test_workflow.final_state:
                failure_reason = (
                    new_failing_test_workflow.final_state.get("failure_reason")
                    or failure_reason
                )

            # Update STATUS to "Failed to Create CL"
            success, _, error = transition_changespec_status(
                project_file, cs_name, "Failed to Create CL", validate=True
            )
            if success:
                print_status(
                    f"Updated STATUS to 'Failed to Create CL' in {project_file}", "info"
                )
            else:
                print_status(f"Warning: Could not update STATUS: {error}", "warning")

            return {
                **state,
                "failure_reason": failure_reason,
            }

        # Now create the CL commit with tags
        cl_id = _create_cl_commit(state, cs_name)
        if not cl_id:
            # Update STATUS to "Failed to Create CL"
            success, _, error = transition_changespec_status(
                project_file, cs_name, "Failed to Create CL", validate=True
            )
            if success:
                print_status(
                    f"Updated STATUS to 'Failed to Create CL' in {project_file}", "info"
                )
            else:
                print_status(f"Warning: Could not update STATUS: {error}", "warning")

            return {
                **state,
                "failure_reason": "Failed to create CL commit",
            }

        # Update the CL field in the project file
        try:
            _update_changespec_cl(project_file, cs_name, cl_id)
        except Exception as e:
            print_status(f"Could not update CL field: {e}", "warning")

        # Update TEST TARGETS field if test targets were extracted
        test_targets = None
        if new_failing_test_workflow.final_state:
            test_targets = new_failing_test_workflow.final_state.get("test_targets")
            if test_targets:
                try:
                    _update_changespec_test_targets(project_file, cs_name, test_targets)
                except Exception as e:
                    print_status(f"Could not update TEST TARGETS field: {e}", "warning")
            else:
                print_status(
                    "ERROR: No test targets found in workflow final state", "error"
                )
                # Update STATUS to "Failed to Create CL"
                success, _, error = transition_changespec_status(
                    project_file, cs_name, "Failed to Create CL", validate=True
                )
                if not success:
                    print_status(
                        f"Warning: Could not update STATUS: {error}", "warning"
                    )
                return {
                    **state,
                    "failure_reason": "new-failing-test workflow did not output TEST TARGETS",
                }

    except Exception as e:
        # Update STATUS to "Failed to Create CL"
        success, _, error = transition_changespec_status(
            project_file, cs_name, "Failed to Create CL", validate=True
        )
        if success:
            print_status(
                f"Updated STATUS to 'Failed to Create CL' in {project_file}", "info"
            )
        else:
            print_status(f"Warning: Could not update STATUS: {error}", "warning")

        return {
            **state,
            "failure_reason": f"Error invoking new-failing-test: {e}",
        }

    # Build test command using rabbit with the TEST TARGETS
    if not test_targets:
        return {
            **state,
            "failure_reason": "TEST TARGETS not available to build test command",
        }

    # Check if TEST TARGETS is "None" (no tests required)
    if test_targets == "None":
        # Still mark as successful and continue
        return state

    test_cmd = f"rabbit test -c opt --no_show_progress {_test_targets_to_command_args(test_targets)}"

    try:
        test_result = run_shell_command(test_cmd, capture_output=True)

        # Save test output to persistent location
        test_output_file = _get_test_output_file_path(project_file, cs_name)
        with open(test_output_file, "w") as f:
            f.write(f"Command: {test_cmd}\n")
            f.write(f"Return code: {test_result.returncode}\n\n")
            f.write("STDOUT:\n")
            f.write(test_result.stdout)
            if test_result.stderr:
                f.write("\n\nSTDERR:\n")
                f.write(test_result.stderr)

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error running test command: {e}",
        }

    # Update status to "TDD CL Created"
    print_status(f"Updating STATUS to 'TDD CL Created' for {cs_name}...", "progress")
    success, _, error = transition_changespec_status(
        project_file, cs_name, "TDD CL Created", validate=True
    )
    if not success:
        return {
            **state,
            "failure_reason": f"Error updating status to 'TDD CL Created': {error}",
        }

    # Mark that we've completed new-failing-test phase
    state["status_updated_to_tdd_cl_created"] = True

    # Update the workflow instance's current state for interrupt handling
    workflow_instance = state.get("workflow_instance")
    if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
        workflow_instance._update_current_state(state)

    # Update tracker to mark that TDD CL was created (reached final state, can untrack)
    if workflow_instance and hasattr(workflow_instance, "_untrack_intermediate_state"):
        workflow_instance._untrack_intermediate_state(project_file, cs_name)

    # Return success - workflow will continue to run fix-tests automatically
    state["success"] = True
    state["cl_id"] = cl_id
    print_status(
        f"Successfully created test CL for {cs_name}. Will continue to fix-tests phase.",
        "success",
    )

    return state


def _run_fix_tests_for_tdd_cl(state: WorkProjectState) -> WorkProjectState:
    """
    Run fix-tests workflow for a "TDD CL Created" ChangeSpec.

    Loads test output from persistent storage, runs fix-tests,
    and updates status to "Pre-Mailed" on success.
    """
    selected_cs = state["selected_changespec"]
    if not selected_cs:
        return {
            **state,
            "failure_reason": "No ChangeSpec selected",
        }

    cs_name = selected_cs.get("NAME", "UNKNOWN")
    cl_id = selected_cs.get("CL", "None")
    project_file = state["project_file"]

    # Update the ChangeSpec STATUS to "Fixing Tests" before running fix-tests
    print_status(f"Updating STATUS to 'Fixing Tests' for {cs_name}...", "progress")
    success, _, error = transition_changespec_status(
        project_file, cs_name, "Fixing Tests", validate=True
    )
    if not success:
        return {
            **state,
            "failure_reason": f"Error updating STATUS: {error}",
        }

    # Mark that we've updated the status so we can revert on interrupt
    state["status_updated_to_fixing_tests"] = True

    # Update the workflow instance's current state for interrupt handling
    workflow_instance = state.get("workflow_instance")
    if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
        workflow_instance._update_current_state(state)

    # Track this intermediate state for cleanup
    if workflow_instance and hasattr(workflow_instance, "_track_intermediate_state"):
        workflow_instance._track_intermediate_state(
            project_file, cs_name, "Fixing Tests", tdd_cl_created=False
        )

    print_status(
        f"Implementing feature for {cs_name} (CL {cl_id}) using fix-tests workflow...",
        "progress",
    )

    # Load test output from persistent storage
    test_output_file = _get_test_output_file_path(project_file, cs_name)
    if not os.path.exists(test_output_file):
        # Update STATUS to "TDD CL Created" (to allow retry)
        success, _, error = transition_changespec_status(
            project_file, cs_name, "TDD CL Created", validate=True
        )
        if success:
            print_status(
                f"Updated STATUS to 'TDD CL Created' in {project_file}", "info"
            )
        else:
            print_status(f"Warning: Could not update STATUS: {error}", "warning")

        return {
            **state,
            "failure_reason": f"Test output file not found: {test_output_file}",
        }

    # Extract test command from saved test output
    test_cmd = None
    try:
        with open(test_output_file) as f:
            first_line = f.readline()
            if first_line.startswith("Command: "):
                test_cmd = first_line.split("Command: ", 1)[1].strip()
    except Exception:
        pass

    # Extract test targets from ChangeSpec
    test_targets_raw = selected_cs.get("TEST TARGETS", "").strip()
    test_targets: str | None = (
        test_targets_raw if test_targets_raw and test_targets_raw != "None" else None
    )

    # If test command not found in file, build it from TEST TARGETS in ChangeSpec
    if not test_cmd:
        if test_targets:
            test_cmd = f"rabbit test -c opt --no_show_progress {_test_targets_to_command_args(test_targets)}"
        else:
            return {
                **state,
                "failure_reason": "Could not determine test command - no command in file and no TEST TARGETS in ChangeSpec",
            }

    try:
        # Create and run the new-tdd-feature workflow
        new_tdd_feature_workflow = NewTddFeatureWorkflow(
            test_output_file=test_output_file,
            test_cmd=test_cmd,
            test_targets=test_targets,
            user_instructions_file=None,
            max_iterations=10,
            context_file_directory=None,  # Will use default (~/.gai/designs/<PROJECT>)
        )

        feature_cl_success = new_tdd_feature_workflow.run()

        if feature_cl_success:
            # Update status to "Pre-Mailed"
            print_status(
                f"Updating STATUS to 'Pre-Mailed' for {cs_name}...", "progress"
            )
            success, _, error = transition_changespec_status(
                project_file, cs_name, "Pre-Mailed", validate=True
            )
            if not success:
                return {
                    **state,
                    "failure_reason": f"Error updating status to 'Pre-Mailed': {error}",
                }

            # Untrack intermediate state (reached final state)
            workflow_instance = state.get("workflow_instance")
            if workflow_instance and hasattr(
                workflow_instance, "_untrack_intermediate_state"
            ):
                workflow_instance._untrack_intermediate_state(project_file, cs_name)

            state["success"] = True
            state["cl_id"] = cl_id
            print_status(f"Successfully implemented feature for {cs_name}", "success")
        else:
            # new-tdd-feature failed
            failure_reason = "new-tdd-feature workflow failed to implement feature"

            # Update STATUS to "TDD CL Created" (to allow retry)
            success, _, error = transition_changespec_status(
                project_file, cs_name, "TDD CL Created", validate=True
            )
            if success:
                print_status(
                    f"Updated STATUS to 'TDD CL Created' in {project_file}", "info"
                )

                # Untrack "Fixing Tests" intermediate state
                workflow_instance = state.get("workflow_instance")
                if workflow_instance and hasattr(
                    workflow_instance, "_untrack_intermediate_state"
                ):
                    workflow_instance._untrack_intermediate_state(project_file, cs_name)
            else:
                print_status(f"Warning: Could not update STATUS: {error}", "warning")

            return {
                **state,
                "failure_reason": failure_reason,
            }

    except Exception as e:
        # Update STATUS to "TDD CL Created" (to allow retry)
        success, _, error = transition_changespec_status(
            project_file, cs_name, "TDD CL Created", validate=True
        )
        if success:
            print_status(
                f"Updated STATUS to 'TDD CL Created' in {project_file}", "info"
            )
        else:
            print_status(f"Warning: Could not update STATUS: {error}", "warning")

        return {
            **state,
            "failure_reason": f"Error invoking new-tdd-feature: {e}",
        }

    return state


def handle_success(state: WorkProjectState) -> WorkProjectState:
    """Handle successful workflow completion for one ChangeSpec."""
    from rich_utils import print_workflow_success

    selected_cs = state.get("selected_changespec")
    cs_name = selected_cs.get("NAME", "UNKNOWN") if selected_cs else "UNKNOWN"

    print_workflow_success(
        "work-projects", f"Successfully completed ChangeSpec: {cs_name}"
    )
    return state


def handle_failure(state: WorkProjectState) -> WorkProjectState:
    """Handle workflow failure for one ChangeSpec."""
    from rich_utils import print_workflow_failure

    failure_reason = state.get("failure_reason", "Unknown error")
    selected_cs = state.get("selected_changespec")
    cs_name = selected_cs.get("NAME", "UNKNOWN") if selected_cs else "UNKNOWN"

    # Don't print error for user skips - just a simple info message
    if failure_reason == "User skipped ChangeSpec":
        # Message already printed in invoke_create_cl, no need to repeat
        pass
    else:
        print_workflow_failure(
            "work-projects", f"Failed to complete ChangeSpec: {cs_name}", failure_reason
        )
    return state


def check_continuation(state: WorkProjectState) -> WorkProjectState:
    """
    Check if the workflow should continue processing more ChangeSpecs.

    Only adds ChangeSpecs to attempted_changespecs if they reached a FINAL state.
    Intermediate states like "TDD CL Created" should be re-processed in the same run.
    """
    # Brief sleep to allow Python to process signals
    time.sleep(0.01)

    selected_cs = state.get("selected_changespec")
    cs_name = selected_cs.get("NAME", "") if selected_cs else ""
    project_file = state.get("project_file", "")

    # Determine if the ChangeSpec reached a final state
    # Final states: Pre-Mailed, Failed to Create CL, Failed to Fix Tests, Mailed, Submitted
    # Intermediate states: TDD CL Created, In Progress, Fixing Tests, Not Started
    is_final_state = False
    current_status = ""

    if cs_name and project_file:
        # Read the current STATUS from the project file
        try:
            with open(project_file) as f:
                content = f.read()

            # Parse to find the STATUS of this ChangeSpec
            lines = content.split("\n")
            in_target_cs = False
            for line in lines:
                if line.startswith("NAME:"):
                    name = line.split(":", 1)[1].strip()
                    in_target_cs = name == cs_name
                elif in_target_cs and line.startswith("STATUS:"):
                    current_status = line.split(":", 1)[1].strip()
                    break

            # Check if we've already attempted this ChangeSpec with the same STATUS
            # If so, we're in an infinite loop - treat as final
            # ONLY enforce this check in yolo mode (to prevent infinite loops in automated runs)
            # In interactive mode, allow user to re-attempt (they can decide)
            yolo = state.get("yolo", False)
            attempted_changespec_statuses = state.get(
                "attempted_changespec_statuses", {}
            )
            if (
                yolo
                and cs_name in attempted_changespec_statuses
                and attempted_changespec_statuses[cs_name] == current_status
            ):
                print_status(
                    f"ChangeSpec {cs_name} already attempted with STATUS '{current_status}' - preventing infinite loop",
                    "warning",
                )
                is_final_state = True

                # If stuck in an intermediate state, clean it up immediately
                workflow_instance = state.get("workflow_instance")
                if current_status == "In Progress":
                    print_status(
                        f"Cleaning up stuck 'In Progress' state for {cs_name}",
                        "warning",
                    )
                    if workflow_instance and hasattr(
                        workflow_instance, "_track_intermediate_state"
                    ):
                        # Force cleanup through the global cleanup mechanism
                        workflow_instance._track_intermediate_state(
                            project_file,
                            cs_name,
                            "In Progress",
                            tdd_cl_created=False,
                        )
                elif current_status == "Fixing Tests":
                    print_status(
                        f"Cleaning up stuck 'Fixing Tests' state for {cs_name}",
                        "warning",
                    )
                    if workflow_instance and hasattr(
                        workflow_instance, "_track_intermediate_state"
                    ):
                        # Force cleanup through the global cleanup mechanism
                        workflow_instance._track_intermediate_state(
                            project_file,
                            cs_name,
                            "Fixing Tests",
                            tdd_cl_created=False,
                        )
            else:
                # Check if this is a final state
                final_states = {
                    "Pre-Mailed",
                    "Failed to Create CL",
                    "Failed to Fix Tests",
                    "Mailed",
                    "Submitted",
                }
                is_final_state = current_status in final_states

                # Don't print "will continue processing" for user skips
                user_skipped = state.get("failure_reason") == "User skipped ChangeSpec"
                if not is_final_state and not user_skipped:
                    print_status(
                        f"ChangeSpec {cs_name} in intermediate state: {current_status} - will continue processing",
                        "info",
                    )
        except Exception as e:
            print_status(
                f"Warning: Could not read current status for {cs_name}: {e}",
                "warning",
            )
            # Assume final state to be safe (prevent infinite loops)
            is_final_state = True

    # Track the STATUS of this ChangeSpec for loop detection
    attempted_changespec_statuses = state.get("attempted_changespec_statuses", {})
    if cs_name and current_status:
        # Update the tracking dict with the current STATUS
        attempted_changespec_statuses = {
            **attempted_changespec_statuses,
            cs_name: current_status,
        }

    # Add to attempted list whenever we've shown it to the user
    # (whether they skipped, quit, or completed it)
    attempted_changespecs = state.get("attempted_changespecs", [])
    user_skipped = state.get("failure_reason") == "User skipped ChangeSpec"
    user_quit = state.get("user_requested_quit", False)

    # Add to attempted list if:
    # 1. Reached a final state (completed successfully)
    # 2. User explicitly skipped it
    # 3. User quit (to avoid re-showing after quit)
    if cs_name and cs_name not in attempted_changespecs:
        if is_final_state or user_skipped or user_quit:
            attempted_changespecs = attempted_changespecs + [cs_name]

    # Only increment counter if reached a final state
    changespecs_processed = state.get("changespecs_processed", 0)
    if is_final_state:
        changespecs_processed += 1

    max_changespecs = state.get("max_changespecs")

    # Check if user requested to quit
    user_requested_quit = state.get("user_requested_quit", False)
    user_requested_prev = state.get("user_requested_prev", False)

    # Determine if we should continue
    should_continue = True

    if user_requested_quit:
        should_continue = False
        print_status("Stopping workflow due to user quit request.", "info")
    elif user_requested_prev:
        # User wants to go back, so continue to allow select_next to handle it
        should_continue = True
    elif max_changespecs is not None and changespecs_processed >= max_changespecs:
        should_continue = False
        print_status(
            f"Reached max_changespecs limit ({max_changespecs}). Stopping workflow.",
            "info",
        )

    # Reset success/failure flags for next iteration
    # Reset current_changespec_index to -1 UNLESS user requested to go back
    # (we need to preserve the index when going back so select_next can decrement it)
    result_state: WorkProjectState = {
        **state,
        "attempted_changespecs": attempted_changespecs,
        "attempted_changespec_statuses": attempted_changespec_statuses,
        "changespecs_processed": changespecs_processed,
        "should_continue": should_continue,
        "success": False,
        "failure_reason": None,
        "selected_changespec": None,
        "status_updated_to_in_progress": False,
        "status_updated_to_tdd_cl_created": False,
        "status_updated_to_fixing_tests": False,
        "current_changespec_index": (
            -1 if not user_requested_prev else state["current_changespec_index"]
        ),
    }

    return result_state


def _parse_project_spec(content: str) -> tuple[str | None, list[dict[str, str]]]:
    """
    Parse a ProjectSpec file into a BUG ID and a list of ChangeSpec dictionaries.

    The first line should be "BUG <BUG_ID>", followed by a blank line, then ChangeSpecs.
    Each ChangeSpec is separated by a blank line and contains fields:
    NAME, DESCRIPTION, PARENT, CL, STATUS

    Returns:
        Tuple of (bug_id, changespecs)
    """
    lines = content.split("\n")
    bug_id = None
    changespecs = []
    current_cs: dict[str, str] = {}
    current_field = None
    current_value_lines: list[str] = []

    # Check if first line is BUG field (handle both "BUG:" and "BUG " formats)
    if lines and (lines[0].startswith("BUG:") or lines[0].startswith("BUG ")):
        if lines[0].startswith("BUG:"):
            bug_id = lines[0][4:].strip()  # Extract bug ID (everything after "BUG:")
        else:
            bug_id = lines[0][4:].strip()  # Extract bug ID (everything after "BUG ")
        lines = lines[1:]  # Remove the BUG line

    for line in lines:
        # Check if this is a field header
        if line and not line.startswith(" ") and ":" in line:
            # Save previous field if exists
            if current_field:
                current_cs[current_field] = "\n".join(current_value_lines).strip()
                current_value_lines = []

            # Parse new field
            field, value = line.split(":", 1)
            current_field = field.strip()
            value = value.strip()

            if value:  # Single-line field value
                current_cs[current_field] = value
                current_field = None
            # else: multi-line field, continue collecting lines

        elif line.startswith("  ") and current_field:
            # Continuation of multi-line field (2-space indented)
            current_value_lines.append(line[2:])  # Remove 2-space indent

        elif not line.strip():
            # Blank line
            if current_field:
                # Special handling for TEST TARGETS - do NOT allow blank lines
                if current_field == "TEST TARGETS":
                    # End the TEST TARGETS field (don't preserve blank line)
                    current_cs[current_field] = "\n".join(current_value_lines).strip()
                    current_field = None
                    current_value_lines = []
                else:
                    # For other multi-line fields (like DESCRIPTION) - preserve blank line
                    current_value_lines.append("")
            else:
                # Blank line between ChangeSpecs - end current ChangeSpec
                if current_cs:
                    changespecs.append(current_cs)
                    current_cs = {}

    # Don't forget the last ChangeSpec if file doesn't end with blank line
    if current_field:
        current_cs[current_field] = "\n".join(current_value_lines).strip()
    if current_cs:
        changespecs.append(current_cs)

    return bug_id, changespecs


def _test_targets_to_command_args(test_targets: str) -> str:
    """Convert multi-line or single-line test targets to space-separated string.

    Args:
        test_targets: Test targets string (can be single-line or multi-line format)

    Returns:
        Space-separated test targets suitable for command line use
    """
    if not test_targets or test_targets == "None":
        return test_targets

    # Split by newlines and filter out empty lines
    targets = [t.strip() for t in test_targets.split("\n")]
    targets = [t for t in targets if t and t != "None"]

    # Join with spaces for command line
    return " ".join(targets)


def _format_changespec(cs: dict[str, str]) -> str:
    """
    Format a ChangeSpec dictionary back into the ChangeSpec text format.

    This is used to pass to create-cl via STDIN.
    """
    lines = []

    # NAME field
    lines.append(f"NAME: {cs.get('NAME', '')}")

    # DESCRIPTION field (multi-line, 2-space indented)
    lines.append("DESCRIPTION:")
    description = cs.get("DESCRIPTION", "")
    for desc_line in description.split("\n"):
        lines.append(f"  {desc_line}")

    # PARENT field
    lines.append(f"PARENT: {cs.get('PARENT', 'None')}")

    # CL field
    lines.append(f"CL: {cs.get('CL', 'None')}")

    # TEST TARGETS field (optional)
    if "TEST TARGETS" in cs:
        test_targets = cs["TEST TARGETS"]
        if test_targets in ("None", "") or "\n" not in test_targets:
            # Single-line format for None, empty, or single target
            lines.append(f"TEST TARGETS: {test_targets}")
        else:
            # Multi-line format
            lines.append("TEST TARGETS:")
            for target in test_targets.split("\n"):
                target = target.strip()
                if target:  # Skip blank lines (defensive, shouldn't exist)
                    lines.append(f"  {target}")

    # STATUS field
    lines.append(f"STATUS: {cs.get('STATUS', 'Not Started')}")

    return "\n".join(lines)


def _format_changespec_with_colors(cs: dict[str, str]) -> Text:
    """
    Format a ChangeSpec dictionary with Rich colors matching the vim syntax highlighting.

    This is used for display in the terminal.
    """
    result = Text()

    # Helper to add a field key
    def add_field_key(text: Text, key: str) -> None:
        text.append(key, style="bold #87D7FF")
        text.append(":", style="bold #808080")

    # NAME field
    name_value = cs.get("NAME", "")
    add_field_key(result, "NAME")
    result.append(" ")
    if name_value and name_value != "None":
        result.append(name_value, style="bold #00D7AF")
    else:
        result.append("None", style="bold #00D7AF")
    result.append("\n")

    # DESCRIPTION field
    add_field_key(result, "DESCRIPTION")
    result.append("\n")
    description = cs.get("DESCRIPTION", "")
    for desc_line in description.split("\n"):
        result.append(f"  {desc_line}", style="#D7D7AF")
        result.append("\n")

    # PARENT field
    parent_value = cs.get("PARENT", "None")
    add_field_key(result, "PARENT")
    result.append(" ")
    if parent_value and parent_value != "None":
        result.append(parent_value, style="bold #00D7AF")
    else:
        result.append("None", style="bold #00D7AF")
    result.append("\n")

    # CL field
    cl_value = cs.get("CL", "None")
    add_field_key(result, "CL")
    result.append(" ")
    if cl_value and cl_value != "None":
        result.append(cl_value, style="bold #5FD7FF")
    else:
        result.append("None", style="bold #5FD7FF")
    result.append("\n")

    # TEST TARGETS field (optional)
    if "TEST TARGETS" in cs:
        test_targets = cs["TEST TARGETS"]

        # Check if single-line or multi-line format
        if test_targets in ("None", "") or "\n" not in test_targets:
            # Single-line format
            add_field_key(result, "TEST TARGETS")
            result.append(" ")
            if test_targets and test_targets != "None":
                result.append(test_targets, style="bold #AFD75F")
            else:
                result.append("None", style="bold #AFD75F")
            result.append("\n")
        else:
            # Multi-line format (like DESCRIPTION)
            add_field_key(result, "TEST TARGETS")
            result.append("\n")
            for target in test_targets.split("\n"):
                target = target.strip()
                if target:  # Skip blank lines (defensive)
                    result.append(f"  {target}", style="bold #AFD75F")
                    result.append("\n")

    # STATUS field
    status_value = cs.get("STATUS", "Not Started")
    add_field_key(result, "STATUS")
    result.append(" ")

    # Color status value based on the status
    status_colors = {
        "Not Started": "#D7AF00",
        "In Progress": "#5FD7FF",
        "TDD CL Created": "#AF87FF",
        "Fixing Tests": "#FFD75F",
        "Pre-Mailed": "#87D700",
        "Mailed": "#00D787",
        "Submitted": "#00AF00",
        "Failed to Create CL": "#FF5F5F",
        "Failed to Fix Tests": "#FF8787",
    }
    status_color = status_colors.get(status_value, "#FFFFFF")
    result.append(status_value, style=f"bold {status_color}")

    return result


def _update_changespec_status(
    project_file: str, changespec_name: str, new_status: str
) -> None:
    """
    Update the STATUS field of a specific ChangeSpec in the project file.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_status: New STATUS value (e.g., "In Progress")
    """
    with open(project_file) as f:
        lines = f.readlines()

    # Find the ChangeSpec and update its STATUS
    updated_lines = []
    in_target_changespec = False
    current_name = None

    for line in lines:
        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name

        # Update STATUS if we're in the target ChangeSpec
        if in_target_changespec and line.startswith("STATUS:"):
            # Replace the STATUS line
            updated_lines.append(f"STATUS: {new_status}\n")
            in_target_changespec = False  # Done updating this ChangeSpec
        else:
            updated_lines.append(line)

    # Write the updated content back to the file
    with open(project_file, "w") as f:
        f.writelines(updated_lines)


def _update_changespec_cl(project_file: str, changespec_name: str, cl_id: str) -> None:
    """
    Update the CL field of a specific ChangeSpec in the project file.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        cl_id: CL-ID value (e.g., changeset hash)
    """
    with open(project_file) as f:
        lines = f.readlines()

    # Find the ChangeSpec and update its CL field
    updated_lines = []
    in_target_changespec = False
    current_name = None

    for line in lines:
        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name

        # Update CL if we're in the target ChangeSpec
        if in_target_changespec and line.startswith("CL:"):
            # Replace the CL line
            updated_lines.append(f"CL: {cl_id}\n")
            in_target_changespec = False  # Done updating this ChangeSpec
        else:
            updated_lines.append(line)

    # Write the updated content back to the file
    with open(project_file, "w") as f:
        f.writelines(updated_lines)


def _update_changespec_test_targets(
    project_file: str, changespec_name: str, test_targets: str
) -> None:
    """
    Update the TEST TARGETS field of a specific ChangeSpec in the project file.

    If the TEST TARGETS field doesn't exist, it will be added after the CL field.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        test_targets: Space-separated test targets (e.g., "//path/to:test1 //path/to:test2")
    """
    with open(project_file) as f:
        lines = f.readlines()

    # Find the ChangeSpec and update/add its TEST TARGETS field
    updated_lines: list[str] = []
    in_target_changespec = False
    current_name = None
    test_targets_updated = False
    last_cl_line_index = None

    for i, line in enumerate(lines):
        # Check if this is a NAME field
        if line.startswith("NAME:"):
            # If we were in the target changespec and didn't find TEST TARGETS, add it
            if (
                in_target_changespec
                and not test_targets_updated
                and last_cl_line_index is not None
            ):
                # Insert TEST TARGETS after CL line
                updated_lines.insert(
                    last_cl_line_index + 1, f"TEST TARGETS: {test_targets}\n"
                )
                test_targets_updated = True

            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name
            last_cl_line_index = None

        # Track CL field location for inserting TEST TARGETS if needed
        if in_target_changespec and line.startswith("CL:"):
            last_cl_line_index = len(updated_lines)

        # Update TEST TARGETS if we're in the target ChangeSpec
        if in_target_changespec and line.startswith("TEST TARGETS:"):
            # Replace the TEST TARGETS line
            updated_lines.append(f"TEST TARGETS: {test_targets}\n")
            test_targets_updated = True
        else:
            updated_lines.append(line)

    # Handle case where we're at the end of file and still in target changespec
    if (
        in_target_changespec
        and not test_targets_updated
        and last_cl_line_index is not None
    ):
        # Insert TEST TARGETS after CL line
        updated_lines.insert(last_cl_line_index + 1, f"TEST TARGETS: {test_targets}\n")

    # Write the updated content back to the file
    with open(project_file, "w") as f:
        f.writelines(updated_lines)


def _create_cl_commit(state: WorkProjectState, cl_name: str) -> str | None:
    """
    Create the CL commit with the required tags.

    Args:
        state: Current workflow state
        cl_name: Name of the CL

    Returns:
        CL ID if successful, None otherwise
    """
    project_name = state["project_name"]
    cl_description = state["cl_description"]
    bug_id = state["bug_id"]
    artifacts_dir = state["artifacts_dir"]

    # Create logfile with full CL description prepended with [PROJECT]
    # and tags at the bottom
    logfile_path = os.path.join(artifacts_dir, "cl_commit_message.txt")
    with open(logfile_path, "w") as f:
        f.write(f"[{project_name}] {cl_description}\n\n")
        f.write("AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT\n")
        f.write(f"BUG={bug_id}\n")
        f.write("MARKDOWN=true\n")
        f.write("R=startblock\n")
        f.write("STARTBLOCK_AUTOSUBMIT=yes\n")
        f.write("WANT_LGTM=all\n")

    # Run hg addremove to track new test files
    addremove_cmd = "hg addremove"
    try:
        addremove_result = run_shell_command(addremove_cmd, capture_output=True)
        if addremove_result.returncode != 0:
            print_status(
                f"Warning: hg addremove failed: {addremove_result.stderr}", "warning"
            )
    except Exception as e:
        print_status(f"Warning: Error running hg addremove: {e}", "warning")

    # Run hg commit command
    commit_cmd = f"hg commit --logfile {logfile_path} --name {cl_name}"

    try:
        result = run_shell_command(commit_cmd, capture_output=True)
        if result.returncode == 0:
            # Upload the CL
            upload_cmd = "hg evolve --any; hg upload tree"
            upload_result = run_shell_command(upload_cmd, capture_output=True)
            if upload_result.returncode != 0:
                print_status(
                    f"Warning: CL upload failed: {upload_result.stderr}", "warning"
                )
                return None

            # Get the CL number
            cl_number_cmd = "branch_number"
            cl_number_result = run_shell_command(cl_number_cmd, capture_output=True)
            if cl_number_result.returncode == 0:
                cl_number = cl_number_result.stdout.strip()
                print_status(f"CL number: {cl_number}", "success")
                return cl_number
            else:
                print_status("Warning: Could not retrieve CL number", "warning")
                return None
        else:
            error_msg = f"hg commit failed: {result.stderr}"
            print_status(error_msg, "error")
            return None
    except Exception as e:
        error_msg = f"Error running hg commit: {e}"
        print_status(error_msg, "error")
        return None


def _run_new_change(state: WorkProjectState) -> WorkProjectState:
    """
    Run new-change workflow for a "Not Started" ChangeSpec with TEST TARGETS: None.

    This workflow implements changes that do not require tests.
    """
    selected_cs = state["selected_changespec"]
    if not selected_cs:
        return {
            **state,
            "failure_reason": "No ChangeSpec selected",
        }

    cs_name = selected_cs.get("NAME", "UNKNOWN")
    project_file = state["project_file"]
    project_name = state["project_name"]
    design_docs_dir = state["design_docs_dir"]
    changespec_text = _format_changespec(selected_cs)

    # Update the ChangeSpec STATUS to "In Progress" in the project file
    print_status(f"Updating STATUS to 'In Progress' for {cs_name}...", "progress")
    success, _, error = transition_changespec_status(
        project_file, cs_name, "In Progress", validate=True
    )
    if not success:
        return {
            **state,
            "failure_reason": f"Error updating STATUS: {error}",
        }

    print_status(f"Updated STATUS in {project_file}", "success")
    state["status_updated_to_in_progress"] = True

    # Update the workflow instance's current state for interrupt handling
    workflow_instance = state.get("workflow_instance")
    if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
        workflow_instance._update_current_state(state)

    # Track this intermediate state for cleanup
    if workflow_instance and hasattr(workflow_instance, "_track_intermediate_state"):
        workflow_instance._track_intermediate_state(
            project_file, cs_name, "In Progress", tdd_cl_created=False
        )

    # Run new-ez-feature workflow
    try:
        # Create and run the new-ez-feature workflow
        new_ez_feature_workflow = NewEzFeatureWorkflow(
            project_name=project_name,
            design_docs_dir=design_docs_dir,
            changespec_text=changespec_text,
            context_file_directory=None,  # Will use default (~/.gai/designs/<PROJECT>)
        )

        change_success = new_ez_feature_workflow.run()

        if not change_success:
            # Get failure reason from final state if available
            failure_reason = "new-ez-feature workflow failed"
            if new_ez_feature_workflow.final_state:
                failure_reason = (
                    new_ez_feature_workflow.final_state.get("failure_reason")
                    or failure_reason
                )

            # Update STATUS to "Failed to Create CL"
            success, _, error = transition_changespec_status(
                project_file, cs_name, "Failed to Create CL", validate=True
            )
            if success:
                print_status(
                    f"Updated STATUS to 'Failed to Create CL' in {project_file}", "info"
                )
            else:
                print_status(f"Warning: Could not update STATUS: {error}", "warning")

            return {
                **state,
                "failure_reason": failure_reason,
            }

        # Create the CL commit with tags
        cl_id = _create_cl_commit(state, cs_name)
        if not cl_id:
            # Update STATUS to "Failed to Create CL"
            success, _, error = transition_changespec_status(
                project_file, cs_name, "Failed to Create CL", validate=True
            )
            if success:
                print_status(
                    f"Updated STATUS to 'Failed to Create CL' in {project_file}", "info"
                )
            else:
                print_status(f"Warning: Could not update STATUS: {error}", "warning")

            return {
                **state,
                "failure_reason": "Failed to create CL commit",
            }

        # Update the CL field in the project file
        try:
            _update_changespec_cl(project_file, cs_name, cl_id)
        except Exception as e:
            print_status(f"Could not update CL field: {e}", "warning")

    except Exception as e:
        # Update STATUS to "Failed to Create CL"
        success, _, error = transition_changespec_status(
            project_file, cs_name, "Failed to Create CL", validate=True
        )
        if success:
            print_status(
                f"Updated STATUS to 'Failed to Create CL' in {project_file}", "info"
            )
        else:
            print_status(f"Warning: Could not update STATUS: {error}", "warning")

        return {
            **state,
            "failure_reason": f"Error invoking new-change: {e}",
        }

    # Update status to "Pre-Mailed" (change complete, ready to mail)
    print_status(f"Updating STATUS to 'Pre-Mailed' for {cs_name}...", "progress")
    success, _, error = transition_changespec_status(
        project_file, cs_name, "Pre-Mailed", validate=True
    )
    if not success:
        return {
            **state,
            "failure_reason": f"Error updating status to 'Pre-Mailed': {error}",
        }

    # Untrack intermediate state (reached final state)
    workflow_instance = state.get("workflow_instance")
    if workflow_instance and hasattr(workflow_instance, "_untrack_intermediate_state"):
        workflow_instance._untrack_intermediate_state(project_file, cs_name)

    # Return success
    state["success"] = True
    state["cl_id"] = cl_id
    print_status(
        f"Successfully implemented changes for {cs_name} (no tests required)",
        "success",
    )

    return state


def _run_fix_tests_with_targets(state: WorkProjectState) -> WorkProjectState:
    """
    Run fix-tests workflow for a "Not Started" ChangeSpec with specific TEST TARGETS.

    This workflow runs fix-tests directly with the specified test targets.
    """
    selected_cs = state["selected_changespec"]
    if not selected_cs:
        return {
            **state,
            "failure_reason": "No ChangeSpec selected",
        }

    cs_name = selected_cs.get("NAME", "UNKNOWN")
    project_file = state["project_file"]
    test_targets = selected_cs.get("TEST TARGETS", "").strip()

    if not test_targets or test_targets == "None":
        return {
            **state,
            "failure_reason": "No valid test targets specified",
        }

    # Update the ChangeSpec STATUS to "In Progress" in the project file
    print_status(f"Updating STATUS to 'In Progress' for {cs_name}...", "progress")
    success, _, error = transition_changespec_status(
        project_file, cs_name, "In Progress", validate=True
    )
    if not success:
        return {
            **state,
            "failure_reason": f"Error updating STATUS: {error}",
        }

    print_status(f"Updated STATUS in {project_file}", "success")
    state["status_updated_to_in_progress"] = True

    # Update the workflow instance's current state for interrupt handling
    workflow_instance = state.get("workflow_instance")
    if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
        workflow_instance._update_current_state(state)

    # Track this intermediate state for cleanup
    if workflow_instance and hasattr(workflow_instance, "_track_intermediate_state"):
        workflow_instance._track_intermediate_state(
            project_file, cs_name, "In Progress", tdd_cl_created=False
        )

    # Construct test command with specified targets
    test_cmd = f"rabbit test -c opt --no_show_progress {_test_targets_to_command_args(test_targets)}"

    # Run tests to capture initial output
    artifacts_dir = state["artifacts_dir"]
    test_output_file = os.path.join(artifacts_dir, "initial_test_output.txt")

    try:
        test_result = run_shell_command(test_cmd, capture_output=True)

        # Save test output to file
        with open(test_output_file, "w") as f:
            f.write(f"Command: {test_cmd}\n")
            f.write(f"Return code: {test_result.returncode}\n\n")
            f.write("STDOUT:\n")
            f.write(test_result.stdout)
            if test_result.stderr:
                f.write("\n\nSTDERR:\n")
                f.write(test_result.stderr)

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error running initial test command: {e}",
        }

    # Update status to "Fixing Tests"
    print_status(f"Updating STATUS to 'Fixing Tests' for {cs_name}...", "progress")
    success, _, error = transition_changespec_status(
        project_file, cs_name, "Fixing Tests", validate=True
    )
    if not success:
        return {
            **state,
            "failure_reason": f"Error updating STATUS: {error}",
        }

    state["status_updated_to_fixing_tests"] = True

    # Update the workflow instance's current state for interrupt handling
    workflow_instance = state.get("workflow_instance")
    if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
        workflow_instance._update_current_state(state)

    # Track this intermediate state for cleanup
    if workflow_instance and hasattr(workflow_instance, "_track_intermediate_state"):
        workflow_instance._track_intermediate_state(
            project_file, cs_name, "Fixing Tests", tdd_cl_created=False
        )

    try:
        # Create and run the fix-tests workflow
        # Note: fix-tests will run its own research agents
        fix_tests_workflow = FixTestsWorkflow(
            test_cmd=test_cmd,
            test_output_file=test_output_file,
            user_instructions_file=None,
            max_iterations=10,
        )

        fix_success = fix_tests_workflow.run()

        if fix_success:
            # Create the CL commit with tags
            cl_id = _create_cl_commit(state, cs_name)
            if not cl_id:
                return {
                    **state,
                    "failure_reason": "Failed to create CL commit",
                }

            # Update the CL field in the project file
            try:
                _update_changespec_cl(project_file, cs_name, cl_id)
            except Exception as e:
                print_status(f"Could not update CL field: {e}", "warning")

            # Update status to "Pre-Mailed"
            print_status(
                f"Updating STATUS to 'Pre-Mailed' for {cs_name}...", "progress"
            )
            success, _, error = transition_changespec_status(
                project_file, cs_name, "Pre-Mailed", validate=True
            )
            if not success:
                return {
                    **state,
                    "failure_reason": f"Error updating status to 'Pre-Mailed': {error}",
                }

            # Untrack intermediate state (reached final state)
            workflow_instance = state.get("workflow_instance")
            if workflow_instance and hasattr(
                workflow_instance, "_untrack_intermediate_state"
            ):
                workflow_instance._untrack_intermediate_state(project_file, cs_name)

            state["success"] = True
            state["cl_id"] = cl_id
            print_status(f"Successfully fixed tests for {cs_name}", "success")
        else:
            # fix-tests failed
            failure_reason = "fix-tests workflow failed to fix tests"

            # Update STATUS to "TDD CL Created" (to allow retry)
            success, _, error = transition_changespec_status(
                project_file, cs_name, "TDD CL Created", validate=True
            )
            if success:
                print_status(
                    f"Updated STATUS to 'TDD CL Created' in {project_file}", "info"
                )

                # Untrack "Fixing Tests" intermediate state
                workflow_instance = state.get("workflow_instance")
                if workflow_instance and hasattr(
                    workflow_instance, "_untrack_intermediate_state"
                ):
                    workflow_instance._untrack_intermediate_state(project_file, cs_name)
            else:
                print_status(f"Warning: Could not update STATUS: {error}", "warning")

            return {
                **state,
                "failure_reason": failure_reason,
            }

    except Exception as e:
        # Update STATUS to "TDD CL Created" (to allow retry)
        success, _, error = transition_changespec_status(
            project_file, cs_name, "TDD CL Created", validate=True
        )
        if success:
            print_status(
                f"Updated STATUS to 'TDD CL Created' in {project_file}", "info"
            )
        else:
            print_status(f"Warning: Could not update STATUS: {error}", "warning")

        return {
            **state,
            "failure_reason": f"Error invoking new-tdd-feature: {e}",
        }

    return state


def _get_test_output_file_path(project_file: str, changespec_name: str) -> str:
    """
    Get the persistent path for storing test output for a ChangeSpec.

    Creates a .test_outputs directory next to the project file if it doesn't exist.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec

    Returns:
        Path to the test output file for this ChangeSpec
    """
    project_dir = os.path.dirname(os.path.abspath(project_file))
    test_outputs_dir = os.path.join(project_dir, ".test_outputs")
    os.makedirs(test_outputs_dir, exist_ok=True)

    # Sanitize changespec name for use in filename
    safe_name = changespec_name.replace("/", "_").replace(" ", "_")
    return os.path.join(test_outputs_dir, f"{safe_name}.txt")

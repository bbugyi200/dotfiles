"""Workflow nodes for the work-projects workflow."""

import os
import sys
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fix_tests_workflow.main import FixTestsWorkflow
from new_ez_feature_workflow.main import NewEzFeatureWorkflow
from new_failing_tests_workflow.main import NewFailingTestWorkflow
from new_tdd_feature_workflow.main import NewTddFeatureWorkflow
from rich_utils import print_status
from shared_utils import (
    create_artifacts_directory,
    generate_workflow_tag,
    initialize_gai_log,
    run_shell_command,
)
from status_state_machine import transition_changespec_status

from .state import WorkProjectState


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
        print_status(
            f"Parsed BUG {bug_id} and {len(changespecs)} ChangeSpecs from {project_file}",
            "success",
        )

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error reading project file: {e}",
        }

    return state


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

    # Build a map of NAME -> ChangeSpec for easy lookup
    changespec_map = {cs.get("NAME", ""): cs for cs in changespecs if cs.get("NAME")}

    # PRIORITY 1: Find the first ChangeSpec with "TDD CL Created" status
    selected_cs = None
    for cs in changespecs:
        name = cs.get("NAME", "")
        status = cs.get("STATUS", "").strip()

        # Skip if no NAME field
        if not name:
            continue

        # Skip if already attempted
        if name in attempted_changespecs:
            print_status(
                f"Skipping ChangeSpec: {name} (already attempted in this run)",
                "info",
            )
            continue

        if status == "TDD CL Created":
            selected_cs = cs
            print_status(
                f"Selected ChangeSpec: {name} (TDD CL Created - ready for fix-tests)",
                "success",
            )

            # Update to this changelist since it already exists
            print_status(f"Updating to changelist: {name}", "progress")
            try:
                result = run_shell_command(f"hg_update {name}", capture_output=True)
                if result.returncode == 0:
                    print_status(f"Successfully updated to: {name}", "success")
                else:
                    error_msg = (
                        f"hg_update to {name} failed with exit code {result.returncode}"
                    )
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
                print_status("Skipping ChangeSpec with no NAME field", "warning")
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
                print_status(f"Selected ChangeSpec: {name} (no parent)", "success")

                # Update to p4head since this is the first CL in the chain
                print_status("Updating to p4head (no parent)", "progress")
                try:
                    result = run_shell_command("hg_update p4head", capture_output=True)
                    if result.returncode == 0:
                        print_status("Successfully updated to p4head", "success")
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
                    print_status(f"Updating to parent changelist: {parent}", "progress")
                    try:
                        result = run_shell_command(
                            f"hg_update {parent}", capture_output=True
                        )
                        if result.returncode == 0:
                            print_status(
                                f"Successfully updated to parent: {parent}",
                                "success",
                            )
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
    print_status(f"Created artifacts directory: {artifacts_dir}", "success")
    print_status(f"Generated workflow tag: {workflow_tag}", "info")

    # Initialize gai.md log
    initialize_gai_log(artifacts_dir, "work-projects", workflow_tag)

    # Run clsurf command if project_name is available
    project_name = state["project_name"]
    clsurf_output_file = None
    if project_name:
        print_status(f"Running clsurf for project: {project_name}", "progress")
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
            print_status(f"Saved clsurf output to: {clsurf_output_file}", "success")
        except Exception as e:
            print_status(f"Warning: Failed to run clsurf command: {e}", "warning")

    return {
        **state,
        "selected_changespec": selected_cs,
        "cl_name": cl_name,
        "cl_description": cl_description,
        "artifacts_dir": artifacts_dir,
        "workflow_tag": workflow_tag,
        "clsurf_output_file": clsurf_output_file,
        "messages": [],
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

    # Format the ChangeSpec for workflows
    changespec_text = _format_changespec(selected_cs)

    # Get the project name and design docs dir
    project_name = state["project_name"]
    design_docs_dir = state["design_docs_dir"]
    yolo = state.get("yolo", False)
    cs_name = selected_cs.get("NAME", "UNKNOWN")
    cs_status = selected_cs.get("STATUS", "").strip()
    test_targets = selected_cs.get("TEST TARGETS", "").strip()

    # ALWAYS print the ChangeSpec before starting work
    from rich.panel import Panel
    from rich_utils import console

    print_status(f"Starting work on ChangeSpec: {cs_name}", "info")
    print_status(f"Project: {project_name}", "info")
    print_status(f"Design docs: {design_docs_dir}", "info")
    print_status(f"Status: {cs_status}", "info")
    print_status(f"Test targets: {test_targets or '(using TDD workflow)'}", "info")

    console.print(
        Panel(
            changespec_text,
            title=f"ChangeSpec: {cs_name}",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # Prompt for confirmation unless yolo mode is enabled
    if not yolo:
        response = input("\nProceed with this ChangeSpec? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print_status(f"Skipping ChangeSpec: {cs_name}", "info")
            state["success"] = False
            state["failure_reason"] = "User skipped ChangeSpec"
            return state

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
        return {
            **state,
            "failure_reason": f"Unexpected ChangeSpec status: {cs_status} (expected 'Not Started' or 'TDD CL Created')",
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

    print_status(f"Updated STATUS in {project_file}", "success")
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
    print_status(f"Creating test CL for {cs_name}...", "progress")
    print_status(f"Project: {project_name}", "info")
    print_status(f"Design docs: {design_docs_dir}", "info")

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

        print_status("New failing test workflow completed successfully", "success")

        # Now create the CL commit with tags
        print_status("Creating CL commit...", "progress")
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

        print_status(f"Captured test CL-ID: {cl_id}", "success")

        # Update the CL field in the project file
        try:
            _update_changespec_cl(project_file, cs_name, cl_id)
            print_status(f"Updated CL field in {project_file}", "success")
        except Exception as e:
            print_status(f"Could not update CL field: {e}", "warning")

        # Update TEST TARGETS field if test targets were extracted
        test_targets = None
        if new_failing_test_workflow.final_state:
            test_targets = new_failing_test_workflow.final_state.get("test_targets")
            if test_targets:
                try:
                    _update_changespec_test_targets(project_file, cs_name, test_targets)
                    print_status(
                        f"Updated TEST TARGETS field in {project_file}", "success"
                    )
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
        print_status("TEST TARGETS is 'None' - no tests to run", "info")
        # Still mark as successful and continue
        return state

    test_cmd = f"rabbit test -c opt --no_show_progress {test_targets}"
    print_status(f"Running test command to capture failures: {test_cmd}", "progress")

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

        print_status(f"Test output saved to: {test_output_file}", "success")

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

    print_status(f"Updated STATUS to 'TDD CL Created' in {project_file}", "success")
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

    print_status(f"Updated STATUS in {project_file}", "success")
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

    print_status(f"Loaded test output from: {test_output_file}", "info")

    # Extract test command from saved test output
    test_cmd = None
    try:
        with open(test_output_file) as f:
            first_line = f.readline()
            if first_line.startswith("Command: "):
                test_cmd = first_line.split("Command: ", 1)[1].strip()
    except Exception:
        pass

    # If test command not found in file, build it from TEST TARGETS in ChangeSpec
    if not test_cmd:
        test_targets = selected_cs.get("TEST TARGETS", "").strip()
        if test_targets and test_targets != "None":
            test_cmd = f"rabbit test -c opt --no_show_progress {test_targets}"
            print_status(
                f"Test command not in file, built from TEST TARGETS: {test_cmd}", "info"
            )
        else:
            return {
                **state,
                "failure_reason": "Could not determine test command - no command in file and no TEST TARGETS in ChangeSpec",
            }

    print_status(f"Using test command: {test_cmd}", "info")

    try:
        # Create and run the new-tdd-feature workflow
        new_tdd_feature_workflow = NewTddFeatureWorkflow(
            test_output_file=test_output_file,
            test_cmd=test_cmd,
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

            print_status(f"Updated STATUS to 'Pre-Mailed' in {project_file}", "success")

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
            attempted_changespec_statuses = state.get(
                "attempted_changespec_statuses", {}
            )
            if (
                cs_name in attempted_changespec_statuses
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

                if is_final_state:
                    print_status(
                        f"ChangeSpec {cs_name} reached final state: {current_status}",
                        "info",
                    )
                else:
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

    # Only add to attempted list if it reached a final state
    attempted_changespecs = state.get("attempted_changespecs", [])
    if cs_name and cs_name not in attempted_changespecs and is_final_state:
        attempted_changespecs = attempted_changespecs + [cs_name]

    # Only increment counter if reached a final state
    changespecs_processed = state.get("changespecs_processed", 0)
    if is_final_state:
        changespecs_processed += 1

    max_changespecs = state.get("max_changespecs")

    # Determine if we should continue
    should_continue = True
    if max_changespecs is not None and changespecs_processed >= max_changespecs:
        should_continue = False
        print_status(
            f"Reached max_changespecs limit ({max_changespecs}). Stopping workflow.",
            "info",
        )
    else:
        print_status(
            f"Processed {changespecs_processed} ChangeSpec(s) to completion. Looking for next eligible ChangeSpec...",
            "info",
        )

    # Reset success/failure flags for next iteration
    return {
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
    }


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
                # Blank line inside a multi-line field - preserve it
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
        lines.append(f"TEST TARGETS: {cs['TEST TARGETS']}")

    # STATUS field
    lines.append(f"STATUS: {cs.get('STATUS', 'Not Started')}")

    return "\n".join(lines)


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

    print_status(f"Created commit message file: {logfile_path}", "success")

    # Run hg addremove to track new test files
    addremove_cmd = "hg addremove"
    print_status(f"Running: {addremove_cmd}", "progress")
    try:
        addremove_result = run_shell_command(addremove_cmd, capture_output=True)
        if addremove_result.returncode == 0:
            print_status("hg addremove completed", "success")
        else:
            print_status(
                f"Warning: hg addremove failed: {addremove_result.stderr}", "warning"
            )
    except Exception as e:
        print_status(f"Warning: Error running hg addremove: {e}", "warning")

    # Run hg commit command
    commit_cmd = f"hg commit --logfile {logfile_path} --name {cl_name}"
    print_status(f"Running: {commit_cmd}", "progress")

    try:
        result = run_shell_command(commit_cmd, capture_output=True)
        if result.returncode == 0:
            print_status("CL commit created successfully", "success")

            # Upload the CL
            print_status("Uploading CL...", "progress")
            upload_cmd = "hg evolve --any; hg upload tree"
            upload_result = run_shell_command(upload_cmd, capture_output=True)
            if upload_result.returncode != 0:
                print_status(
                    f"Warning: CL upload failed: {upload_result.stderr}", "warning"
                )
                return None

            print_status("CL uploaded successfully", "success")

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
    print_status(
        f"Implementing changes for {cs_name} (no tests required)...", "progress"
    )
    print_status(f"Project: {project_name}", "info")
    print_status(f"Design docs: {design_docs_dir}", "info")

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

        print_status("New change workflow completed successfully", "success")

        # Create the CL commit with tags
        print_status("Creating CL commit...", "progress")
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

        print_status(f"Captured CL-ID: {cl_id}", "success")

        # Update the CL field in the project file
        try:
            _update_changespec_cl(project_file, cs_name, cl_id)
            print_status(f"Updated CL field in {project_file}", "success")
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

    print_status(f"Updated STATUS to 'Pre-Mailed' in {project_file}", "success")

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
    test_cmd = f"rabbit test -c opt --no_show_progress {test_targets}"
    print_status(f"Running tests with targets: {test_targets}", "progress")
    print_status(f"Test command: {test_cmd}", "info")

    # Run tests to capture initial output
    artifacts_dir = state["artifacts_dir"]
    test_output_file = os.path.join(artifacts_dir, "initial_test_output.txt")
    print_status("Running tests to capture initial output...", "progress")

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

        print_status(f"Test output saved to: {test_output_file}", "success")

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

    print_status(f"Updated STATUS in {project_file}", "success")
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
            print_status("Creating CL commit...", "progress")
            cl_id = _create_cl_commit(state, cs_name)
            if not cl_id:
                return {
                    **state,
                    "failure_reason": "Failed to create CL commit",
                }

            print_status(f"Captured CL-ID: {cl_id}", "success")

            # Update the CL field in the project file
            try:
                _update_changespec_cl(project_file, cs_name, cl_id)
                print_status(f"Updated CL field in {project_file}", "success")
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

            print_status(f"Updated STATUS to 'Pre-Mailed' in {project_file}", "success")

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

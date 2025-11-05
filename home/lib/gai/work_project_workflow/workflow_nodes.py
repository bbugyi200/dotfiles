"""Workflow nodes for the work-project workflow."""

import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fix_tests_workflow.main import FixTestsWorkflow
from new_change_workflow.main import NewChangeWorkflow
from new_failing_test_workflow.main import NewFailingTestWorkflow
from rich_utils import print_status
from shared_utils import (
    create_artifacts_directory,
    generate_workflow_tag,
    initialize_gai_log,
    run_shell_command,
)

from .state import WorkProjectState


def initialize_work_project_workflow(state: WorkProjectState) -> WorkProjectState:
    """
    Initialize the work-project workflow.

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

    Also creates artifacts directory and extracts ChangeSpec fields.
    """
    changespecs = state["changespecs"]

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

        if status == "TDD CL Created":
            selected_cs = cs
            print_status(
                f"Selected ChangeSpec: {name} (TDD CL Created - ready for fix-tests)",
                "success",
            )
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

            # Skip if not "Not Started"
            if status != "Not Started":
                continue

            # Check if no parent or parent is completed
            if parent == "None":
                # No parent - eligible
                selected_cs = cs
                print_status(f"Selected ChangeSpec: {name} (no parent)", "success")
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
                                f"Successfully updated to parent: {parent}", "success"
                            )
                        else:
                            print_status(
                                f"Warning: hg_update to {parent} returned non-zero exit code: {result.returncode}",
                                "warning",
                            )
                            if result.stderr:
                                print_status(f"stderr: {result.stderr}", "warning")
                    except Exception as e:
                        print_status(
                            f"Warning: Failed to update to parent {parent}: {e}",
                            "warning",
                        )

                    break

    if not selected_cs:
        # No eligible ChangeSpec found
        return {
            **state,
            "failure_reason": "No eligible ChangeSpec found (all are either completed or blocked by incomplete parents)",
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
    initialize_gai_log(artifacts_dir, "work-project", workflow_tag)

    # Run clsurf command if project_name is available
    project_name = state["project_name"]
    clsurf_output_file = None
    if project_name:
        print_status(f"Running clsurf for project: {project_name}", "progress")
        clsurf_cmd = f"clsurf 'a:me is:submitted {project_name}'"
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


def save_research_results(state: WorkProjectState) -> WorkProjectState:
    """
    Save research results to a file that can be referenced with @ paths.

    Creates a single aggregated research file from all research agent results.
    """
    research_results = state.get("research_results")
    if not research_results:
        return {
            **state,
            "failure_reason": "No research results to save",
        }

    artifacts_dir = state["artifacts_dir"]
    research_file = os.path.join(artifacts_dir, "research_aggregated.md")

    print_status(f"Saving research results to: {research_file}", "progress")

    try:
        with open(research_file, "w") as f:
            f.write("# Aggregated Research Results\n\n")
            f.write(
                "This file contains research findings from all research agents run by the work-project workflow.\n\n"
            )

            for focus, result in research_results.items():
                f.write(f"## {result['title']}\n\n")
                f.write(f"{result['content']}\n\n")
                f.write("---\n\n")

        print_status(f"Research results saved to: {research_file}", "success")

        return {
            **state,
            "research_file": research_file,
        }

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error saving research results: {e}",
        }


def create_context_directory(state: WorkProjectState) -> WorkProjectState:
    """
    Create a context directory with markdown files describing the TDD workflow.

    This directory will be passed to fix-tests via the -D option.
    """
    artifacts_dir = state["artifacts_dir"]
    context_dir = os.path.join(artifacts_dir, "context")

    print_status(f"Creating context directory: {context_dir}", "progress")

    try:
        os.makedirs(context_dir, exist_ok=True)

        # Create tdd_workflow.md describing the TDD workflow and current state
        tdd_workflow_file = os.path.join(context_dir, "tdd_workflow.md")
        cl_name = state["cl_name"]
        cl_description = state["cl_description"]

        with open(tdd_workflow_file, "w") as f:
            f.write("# TDD Workflow Context\n\n")
            f.write("## Workflow Overview\n\n")
            f.write(
                "This CL is being developed using Test-Driven Development (TDD):\n\n"
            )
            f.write("1. **Tests Created First** (COMPLETED)\n")
            f.write(
                "   - Failing tests have been added to validate the feature described below\n"
            )
            f.write("   - These tests verify the expected behavior of the feature\n")
            f.write("   - Tests are currently FAILING (as expected in TDD)\n\n")
            f.write("2. **Feature Implementation** (CURRENT STEP)\n")
            f.write(
                "   - You are now responsible for implementing the feature to make the tests pass\n"
            )
            f.write(
                "   - Modify production code, configuration, or infrastructure as needed\n"
            )
            f.write(
                "   - The tests should pass once you've correctly implemented the feature\n\n"
            )
            f.write("3. **Verification** (NEXT STEP)\n")
            f.write("   - After implementation, all tests must pass\n")
            f.write(
                "   - The workflow will verify that tests now pass successfully\n\n"
            )
            f.write("## Feature Description\n\n")
            f.write(f"**Feature Name:** {cl_name}\n\n")
            f.write(f"**Description:**\n\n{cl_description}\n\n")
            f.write("## Your Task\n\n")
            f.write(
                "Implement the feature described above to make the failing tests pass.\n"
            )
            f.write("Review the test failures carefully to understand:\n")
            f.write("- What functionality is being tested\n")
            f.write("- What the tests expect from your implementation\n")
            f.write("- What changes are needed to satisfy the test requirements\n\n")
            f.write("## Important Notes\n\n")
            f.write("- Do NOT modify or delete the new tests that were added\n")
            f.write(
                "- Focus on implementing the feature, not working around the tests\n"
            )
            f.write(
                "- The tests define the expected behavior - make your code match it\n"
            )

        print_status(f"Created TDD workflow context: {tdd_workflow_file}", "success")

        return {
            **state,
            "context_dir": context_dir,
        }

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error creating context directory: {e}",
        }


def invoke_create_cl(state: WorkProjectState) -> WorkProjectState:
    """
    Invoke the appropriate workflow based on ChangeSpec status and TEST TARGETS.

    For "Not Started" ChangeSpecs:
    - If TEST TARGETS is "None": Run new-change workflow (no tests required)
    - If TEST TARGETS has targets: Run fix-tests workflow with those targets
    - If TEST TARGETS is omitted: Use TDD workflow (new-failing-test -> fix-tests)

    For "TDD CL Created" ChangeSpecs:
    1. Load test output from persistent storage
    2. Implement feature to make tests pass (fix-tests)
    3. Update status to "Pre-Mailed" on success

    If dry_run is True, just prints the ChangeSpec without invoking workflows.
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
    dry_run = state.get("dry_run", False)
    cs_name = selected_cs.get("NAME", "UNKNOWN")
    cs_status = selected_cs.get("STATUS", "").strip()
    test_targets = selected_cs.get("TEST TARGETS", "").strip()

    if dry_run:
        # Dry run mode - just print the ChangeSpec
        from rich.panel import Panel
        from rich_utils import console

        print_status(f"[DRY RUN] Would invoke workflows for {cs_name}", "info")
        print_status(f"Project: {project_name}", "info")
        print_status(f"Design docs: {design_docs_dir}", "info")
        print_status(f"Test targets: {test_targets or '(using TDD workflow)'}", "info")

        console.print(
            Panel(
                changespec_text,
                title="ChangeSpec that would be sent to workflows",
                border_style="yellow",
                padding=(1, 2),
            )
        )
        state["success"] = True
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
    try:
        _update_changespec_status(project_file, cs_name, "In Progress")
        print_status(f"Updated STATUS in {project_file}", "success")
        # Mark that we've updated the status so we can revert on interrupt
        state["status_updated_to_in_progress"] = True

        # Update the workflow instance's current state for interrupt handling
        workflow_instance = state.get("workflow_instance")
        if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
            workflow_instance._update_current_state(state)
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error updating project file: {e}",
        }

    # Create test CL with failing tests
    print_status(f"Creating test CL for {cs_name}...", "progress")
    print_status(f"Project: {project_name}", "info")
    print_status(f"Design docs: {design_docs_dir}", "info")

    try:
        # Get research file from state to pass to new-failing-test
        research_file = state.get("research_file")
        if not research_file:
            return {
                **state,
                "failure_reason": "No research file available for new-failing-test workflow",
            }

        # Create and run the new-failing-test workflow
        new_failing_test_workflow = NewFailingTestWorkflow(
            project_name=project_name,
            design_docs_dir=design_docs_dir,
            changespec_text=changespec_text,
            research_file=research_file,
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

            return {
                **state,
                "failure_reason": failure_reason,
            }

        print_status("New failing test workflow completed successfully", "success")

        # Now create the CL commit with tags
        print_status("Creating CL commit...", "progress")
        cl_id = _create_cl_commit(state, cs_name)
        if not cl_id:
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

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error invoking new-failing-test: {e}",
        }

    # Run tests to capture the failure output for later fix-tests run
    test_cmd = "make test"  # Default test command
    if new_failing_test_workflow.final_state:
        test_cmd = new_failing_test_workflow.final_state.get("test_cmd") or "make test"
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
    try:
        _update_changespec_status(project_file, cs_name, "TDD CL Created")
        print_status(f"Updated STATUS to 'TDD CL Created' in {project_file}", "success")
        # Mark that we've completed new-failing-test phase
        state["status_updated_to_tdd_cl_created"] = True

        # Update the workflow instance's current state for interrupt handling
        workflow_instance = state.get("workflow_instance")
        if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
            workflow_instance._update_current_state(state)
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error updating status to 'TDD CL Created': {e}",
        }

    # Return success - fix-tests will run in next work-projects invocation
    state["success"] = True
    state["cl_id"] = cl_id
    print_status(
        f"Successfully created test CL for {cs_name}. Run work-projects again to run fix-tests.",
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
    try:
        _update_changespec_status(project_file, cs_name, "Fixing Tests")
        print_status(f"Updated STATUS in {project_file}", "success")
        # Mark that we've updated the status so we can revert on interrupt
        state["status_updated_to_fixing_tests"] = True

        # Update the workflow instance's current state for interrupt handling
        workflow_instance = state.get("workflow_instance")
        if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
            workflow_instance._update_current_state(state)
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error updating project file: {e}",
        }

    print_status(
        f"Implementing feature for {cs_name} (CL {cl_id}) using fix-tests workflow...",
        "progress",
    )

    # Load test output from persistent storage
    test_output_file = _get_test_output_file_path(project_file, cs_name)
    if not os.path.exists(test_output_file):
        return {
            **state,
            "failure_reason": f"Test output file not found: {test_output_file}",
        }

    print_status(f"Loaded test output from: {test_output_file}", "info")

    # Extract test command from saved test output
    test_cmd = "make test"  # Default
    try:
        with open(test_output_file) as f:
            first_line = f.readline()
            if first_line.startswith("Command: "):
                test_cmd = first_line.split("Command: ", 1)[1].strip()
    except Exception:
        pass  # Use default if we can't read it

    print_status(f"Using test command: {test_cmd}", "info")

    try:
        # Get research file and context directory from state
        research_file = state.get("research_file")
        context_dir = state.get("context_dir")

        if not research_file:
            return {
                **state,
                "failure_reason": "No research file available for fix-tests workflow",
            }

        if not context_dir:
            return {
                **state,
                "failure_reason": "No context directory available for fix-tests workflow",
            }

        # Create and run the fix-tests workflow
        fix_tests_workflow = FixTestsWorkflow(
            test_cmd=test_cmd,
            test_output_file=test_output_file,
            user_instructions_file=None,  # Not using user instructions
            max_iterations=10,
            clquery=None,  # Not using clquery (research already done)
            initial_research_file=research_file,  # Pass research file
            context_file_directory=context_dir,  # Pass context directory
        )

        feature_cl_success = fix_tests_workflow.run()

        if feature_cl_success:
            # Update status to "Pre-Mailed"
            print_status(
                f"Updating STATUS to 'Pre-Mailed' for {cs_name}...", "progress"
            )
            try:
                _update_changespec_status(project_file, cs_name, "Pre-Mailed")
                print_status(
                    f"Updated STATUS to 'Pre-Mailed' in {project_file}", "success"
                )
            except Exception as e:
                return {
                    **state,
                    "failure_reason": f"Error updating status to 'Pre-Mailed': {e}",
                }

            state["success"] = True
            state["cl_id"] = cl_id
            print_status(f"Successfully implemented feature for {cs_name}", "success")
        else:
            # fix-tests failed
            failure_reason = "fix-tests workflow failed to fix tests"

            return {
                **state,
                "failure_reason": failure_reason,
            }

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error invoking fix-tests: {e}",
        }

    return state


def handle_success(state: WorkProjectState) -> WorkProjectState:
    """Handle successful workflow completion."""
    from rich_utils import print_workflow_success

    print_workflow_success(
        "work-project", "Work-project workflow completed successfully!"
    )
    return state


def handle_failure(state: WorkProjectState) -> WorkProjectState:
    """Handle workflow failure."""
    from rich_utils import print_workflow_failure

    failure_reason = state.get("failure_reason", "Unknown error")
    print_workflow_failure(
        "work-project", "Work-project workflow failed", failure_reason
    )
    return state


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
    try:
        _update_changespec_status(project_file, cs_name, "In Progress")
        print_status(f"Updated STATUS in {project_file}", "success")
        state["status_updated_to_in_progress"] = True

        # Update the workflow instance's current state for interrupt handling
        workflow_instance = state.get("workflow_instance")
        if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
            workflow_instance._update_current_state(state)
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error updating project file: {e}",
        }

    # Run new-change workflow
    print_status(
        f"Implementing changes for {cs_name} (no tests required)...", "progress"
    )
    print_status(f"Project: {project_name}", "info")
    print_status(f"Design docs: {design_docs_dir}", "info")

    try:
        # Get research file from state to pass to new-change
        research_file = state.get("research_file")
        if not research_file:
            return {
                **state,
                "failure_reason": "No research file available for new-change workflow",
            }

        # Create and run the new-change workflow
        new_change_workflow = NewChangeWorkflow(
            project_name=project_name,
            design_docs_dir=design_docs_dir,
            changespec_text=changespec_text,
            research_file=research_file,
        )

        change_success = new_change_workflow.run()

        if not change_success:
            # Get failure reason from final state if available
            failure_reason = "new-change workflow failed"
            if new_change_workflow.final_state:
                failure_reason = (
                    new_change_workflow.final_state.get("failure_reason")
                    or failure_reason
                )

            return {
                **state,
                "failure_reason": failure_reason,
            }

        print_status("New change workflow completed successfully", "success")

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

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error invoking new-change: {e}",
        }

    # Update status to "Pre-Mailed" (change complete, ready to mail)
    print_status(f"Updating STATUS to 'Pre-Mailed' for {cs_name}...", "progress")
    try:
        _update_changespec_status(project_file, cs_name, "Pre-Mailed")
        print_status(f"Updated STATUS to 'Pre-Mailed' in {project_file}", "success")
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error updating status to 'Pre-Mailed': {e}",
        }

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
    try:
        _update_changespec_status(project_file, cs_name, "In Progress")
        print_status(f"Updated STATUS in {project_file}", "success")
        state["status_updated_to_in_progress"] = True

        # Update the workflow instance's current state for interrupt handling
        workflow_instance = state.get("workflow_instance")
        if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
            workflow_instance._update_current_state(state)
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error updating project file: {e}",
        }

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
    try:
        _update_changespec_status(project_file, cs_name, "Fixing Tests")
        print_status(f"Updated STATUS in {project_file}", "success")
        state["status_updated_to_fixing_tests"] = True

        # Update the workflow instance's current state for interrupt handling
        workflow_instance = state.get("workflow_instance")
        if workflow_instance and hasattr(workflow_instance, "_update_current_state"):
            workflow_instance._update_current_state(state)
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error updating project file: {e}",
        }

    try:
        # Get research file and context directory from state
        research_file = state.get("research_file")
        context_dir = state.get("context_dir")

        if not research_file:
            return {
                **state,
                "failure_reason": "No research file available for fix-tests workflow",
            }

        if not context_dir:
            return {
                **state,
                "failure_reason": "No context directory available for fix-tests workflow",
            }

        # Create and run the fix-tests workflow
        fix_tests_workflow = FixTestsWorkflow(
            test_cmd=test_cmd,
            test_output_file=test_output_file,  # Use the test output we captured
            user_instructions_file=None,  # Not using user instructions
            max_iterations=10,
            clquery=None,  # Not using clquery (research already done)
            initial_research_file=research_file,  # Pass research file
            context_file_directory=context_dir,  # Pass context directory
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
            try:
                _update_changespec_status(project_file, cs_name, "Pre-Mailed")
                print_status(
                    f"Updated STATUS to 'Pre-Mailed' in {project_file}", "success"
                )
            except Exception as e:
                return {
                    **state,
                    "failure_reason": f"Error updating status to 'Pre-Mailed': {e}",
                }

            state["success"] = True
            state["cl_id"] = cl_id
            print_status(f"Successfully fixed tests for {cs_name}", "success")
        else:
            # fix-tests failed
            failure_reason = "fix-tests workflow failed to fix tests"

            return {
                **state,
                "failure_reason": failure_reason,
            }

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error invoking fix-tests: {e}",
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

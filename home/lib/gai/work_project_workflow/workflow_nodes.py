"""Workflow nodes for the work-project workflow."""

import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from create_test_cl_workflow.main import CreateTestCLWorkflow
from fix_tests_workflow.main import FixTestsWorkflow
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

        changespecs = _parse_project_spec(content)
        if not changespecs:
            return {
                **state,
                "failure_reason": "No ChangeSpecs found in project file",
            }

        state["changespecs"] = changespecs
        print_status(
            f"Parsed {len(changespecs)} ChangeSpecs from {project_file}", "success"
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

    Finds the FIRST "Not Started" ChangeSpec that either:
    - Does NOT have any parent (PARENT == "None"), OR
    - Has a parent ChangeSpec that is "Pre-Mailed", "Mailed", or "Submitted"

    Also creates artifacts directory and extracts ChangeSpec fields.
    """
    changespecs = state["changespecs"]

    # Build a map of NAME -> ChangeSpec for easy lookup
    changespec_map = {cs.get("NAME", ""): cs for cs in changespecs if cs.get("NAME")}

    # Find the first eligible ChangeSpec
    selected_cs = None
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
    Invoke the create-test-cl and pre-mail-cl workflows with the selected ChangeSpec.

    This implements the TDD workflow:
    1. Create test CL with failing tests (create-test-cl)
    2. Implement feature to make tests pass (pre-mail-cl)

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
    project_file = state["project_file"]
    dry_run = state.get("dry_run", False)
    cs_name = selected_cs.get("NAME", "UNKNOWN")

    if dry_run:
        # Dry run mode - just print the ChangeSpec
        from rich.panel import Panel
        from rich_utils import console

        print_status(f"[DRY RUN] Would invoke workflows for {cs_name}", "info")
        print_status(f"Project: {project_name}", "info")
        print_status(f"Design docs: {design_docs_dir}", "info")

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

    # STEP 1: Create test CL with failing tests
    print_status(f"[STEP 1/2] Creating test CL for {cs_name}...", "progress")
    print_status(f"Project: {project_name}", "info")
    print_status(f"Design docs: {design_docs_dir}", "info")

    try:
        # Get research file from state to pass to create-test-cl
        research_file = state.get("research_file")
        if not research_file:
            return {
                **state,
                "failure_reason": "No research file available for create-test-cl workflow",
            }

        # Create and run the create-test-cl workflow
        create_test_cl_workflow = CreateTestCLWorkflow(
            project_name=project_name,
            design_docs_dir=design_docs_dir,
            changespec_text=changespec_text,
            research_file=research_file,  # Pass research file
        )

        test_cl_success = create_test_cl_workflow.run()

        if not test_cl_success:
            # Get failure reason from final state if available
            failure_reason = "create-test-cl workflow failed"
            if create_test_cl_workflow.final_state:
                failure_reason = (
                    create_test_cl_workflow.final_state.get("failure_reason")
                    or failure_reason
                )

            return {
                **state,
                "failure_reason": failure_reason,
            }

        # Get the CL-ID from the final state
        cl_id = None
        if create_test_cl_workflow.final_state:
            cl_id = create_test_cl_workflow.final_state.get("cl_id")
        if not cl_id:
            return {
                **state,
                "failure_reason": "create-test-cl succeeded but no CL-ID was returned",
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
            "failure_reason": f"Error invoking create-test-cl: {e}",
        }

    # STEP 2: Implement feature to make tests pass using fix-tests workflow
    print_status(
        f"[STEP 2/2] Implementing feature for {cs_name} (CL {cl_id}) using fix-tests workflow...",
        "progress",
    )

    # Run the test command to get the actual test failure output
    # The tests should fail since we haven't implemented the feature yet
    test_cmd = "make test"  # Default test command
    if create_test_cl_workflow.final_state:
        test_cmd = create_test_cl_workflow.final_state.get("test_cmd") or "make test"
    print_status(f"Running test command to capture failures: {test_cmd}", "progress")

    try:
        test_result = run_shell_command(test_cmd, capture_output=True)

        # Create test output file for fix-tests workflow
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, dir="/tmp"
        ) as f:
            f.write(f"Command: {test_cmd}\n")
            f.write(f"Return code: {test_result.returncode}\n\n")
            f.write("STDOUT:\n")
            f.write(test_result.stdout)
            if test_result.stderr:
                f.write("\n\nSTDERR:\n")
                f.write(test_result.stderr)
            test_output_file = f.name

        print_status(f"Test output saved to: {test_output_file}", "info")

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error running test command: {e}",
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
            test_output_file=test_output_file,
            user_instructions_file=None,  # Not using user instructions
            max_iterations=10,
            clquery=None,  # Not using clquery (research already done)
            initial_research_file=research_file,  # Pass research file
            context_file_directory=context_dir,  # Pass context directory
        )

        feature_cl_success = fix_tests_workflow.run()

        # Clean up temp file
        try:
            os.unlink(test_output_file)
        except Exception:
            pass  # Ignore cleanup errors

        if feature_cl_success:
            state["success"] = True
            state["cl_id"] = cl_id
            print_status(
                f"Successfully created and implemented CL for {cs_name}", "success"
            )
        else:
            # fix-tests failed
            failure_reason = "fix-tests workflow failed to fix tests"

            return {
                **state,
                "failure_reason": failure_reason,
            }

    except Exception as e:
        # Clean up temp file if it exists
        try:
            if "test_output_file" in locals():
                os.unlink(test_output_file)
        except Exception:
            pass  # Ignore cleanup errors

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


def _parse_project_spec(content: str) -> list[dict[str, str]]:
    """
    Parse a ProjectSpec file into a list of ChangeSpec dictionaries.

    Each ChangeSpec is separated by a blank line and contains fields:
    NAME, DESCRIPTION, PARENT, CL, STATUS
    """
    changespecs = []
    current_cs: dict[str, str] = {}
    current_field = None
    current_value_lines: list[str] = []

    for line in content.split("\n"):
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

    return changespecs


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

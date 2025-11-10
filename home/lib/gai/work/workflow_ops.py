"""Workflow-specific operations for ChangeSpecs."""

import os
import subprocess
import sys
import tempfile

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from new_tdd_feature_workflow.main import NewTddFeatureWorkflow
from status_state_machine import transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs
from .field_updates import _extract_tap_url_from_output, update_tap_field
from .operations import update_to_changespec


def unblock_child_changespecs(
    parent_changespec: ChangeSpec, console: Console | None = None
) -> int:
    """Unblock child ChangeSpecs when parent is moved to Pre-Mailed.

    When a ChangeSpec is moved to "Pre-Mailed", any ChangeSpecs that:
    - Have STATUS of "Blocked (EZ)" or "Blocked (TDD)"
    - Have PARENT field equal to the NAME of the parent ChangeSpec

    Will automatically have their STATUS changed to the corresponding Unstarted status:
    - "Blocked (EZ)" -> "Unstarted (EZ)"
    - "Blocked (TDD)" -> "Unstarted (TDD)"

    Args:
        parent_changespec: The ChangeSpec that was moved to Pre-Mailed
        console: Optional Rich Console for output

    Returns:
        Number of child ChangeSpecs that were unblocked
    """
    # Find all ChangeSpecs
    all_changespecs = find_all_changespecs()

    # Filter for blocked children of this parent
    blocked_children = [
        cs
        for cs in all_changespecs
        if cs.status in ["Blocked (EZ)", "Blocked (TDD)"]
        and cs.parent == parent_changespec.name
    ]

    if not blocked_children:
        return 0

    # Unblock each child
    unblocked_count = 0
    for child in blocked_children:
        # Determine the new status
        new_status = (
            "Unstarted (EZ)" if child.status == "Blocked (EZ)" else "Unstarted (TDD)"
        )

        # Update the status
        success, old_status, error_msg = transition_changespec_status(
            child.file_path,
            child.name,
            new_status,
            validate=False,  # Don't validate - we know this transition is valid
        )

        if success:
            unblocked_count += 1
            if console:
                console.print(
                    f"[green]Unblocked child ChangeSpec '{child.name}': {old_status} → {new_status}[/green]"
                )
        else:
            if console:
                console.print(
                    f"[yellow]Warning: Failed to unblock '{child.name}': {error_msg}[/yellow]"
                )

    return unblocked_count


def run_tdd_feature_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run new-tdd-feature workflow for 'TDD CL Created' status.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Validate that test_targets is set
    if not changespec.test_targets:
        console.print(
            "[red]Error: TEST TARGETS field is not set. Cannot run new-tdd-feature workflow.[/red]"
        )
        return False

    # Convert test_targets list to space-separated string
    test_targets_str = " ".join(changespec.test_targets)

    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Update to the changespec (cd and bb_hg_update)
    success, error_msg = update_to_changespec(changespec, console)
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        return False

    # Get target directory for running workflow and tests
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
    # These should be set since update_to_changespec already validated them
    assert goog_cloud_dir is not None
    assert goog_src_dir_base is not None
    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Generate test output file before running workflow
    console.print("[cyan]Running tests to generate test output file...[/cyan]")
    test_output_file = os.path.join(
        tempfile.gettempdir(), f"test_output_{changespec.name}.txt"
    )
    try:
        test_cmd = f"bb_rabbit_tests {test_targets_str}"
        result = subprocess.run(
            test_cmd,
            shell=True,
            cwd=target_dir,
            capture_output=True,
            text=True,
        )
        # Write test output to file
        with open(test_output_file, "w") as f:
            f.write(f"Test command: {test_cmd}\n")
            f.write(f"Return code: {result.returncode}\n\n")
            f.write("=== STDOUT ===\n")
            f.write(result.stdout)
            f.write("\n=== STDERR ===\n")
            f.write(result.stderr)
        console.print(f"[green]Test output saved to: {test_output_file}[/green]")
    except Exception as e:
        console.print(f"[red]Error generating test output: {str(e)}[/red]")
        return False

    # Update STATUS to "Fixing Tests"
    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        "Fixing Tests",
        validate=True,
    )
    if not success:
        console.print(f"[red]Error updating status: {error_msg}[/red]")
        return False

    # Track whether workflow succeeded for proper rollback
    workflow_succeeded = False

    try:
        # Run new-tdd-feature workflow
        console.print("[cyan]Running new-tdd-feature workflow...[/cyan]")
        workflow = NewTddFeatureWorkflow(
            test_output_file=test_output_file,
            test_targets=test_targets_str,
            user_instructions_file=None,
            max_iterations=10,
            context_file_directory=None,
        )
        workflow_succeeded = workflow.run()

        if workflow_succeeded:
            console.print("[green]Workflow completed successfully![/green]")

            # Run bb_rabbit_tests to check if tests pass
            console.print(
                f"[cyan]Running tests: bb_rabbit_tests {test_targets_str}[/cyan]"
            )
            try:
                result = subprocess.run(
                    f"bb_rabbit_tests {test_targets_str}",
                    shell=True,
                    cwd=target_dir,
                    capture_output=True,
                    text=True,
                )
                tests_passed = result.returncode == 0

                if tests_passed:
                    console.print("[green]Tests passed![/green]")

                    # Run bb_hg_presubmit
                    console.print("[cyan]Running bb_hg_presubmit...[/cyan]")
                    try:
                        result = subprocess.run(
                            ["bb_hg_presubmit"],
                            cwd=target_dir,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        console.print(
                            "[green]bb_hg_presubmit completed successfully![/green]"
                        )
                        # Extract and store TAP URL from output
                        tap_url = _extract_tap_url_from_output(
                            result.stdout + result.stderr
                        )
                        if tap_url:
                            success, error_msg = update_tap_field(
                                changespec.file_path, changespec.name, tap_url
                            )
                            if success:
                                console.print(
                                    f"[green]TAP URL saved: {tap_url}[/green]"
                                )
                            else:
                                console.print(
                                    f"[yellow]Warning: Could not save TAP URL: {error_msg}[/yellow]"
                                )
                    except subprocess.CalledProcessError as e:
                        console.print(
                            f"[yellow]Warning: bb_hg_presubmit failed (exit code {e.returncode})[/yellow]"
                        )
                    except FileNotFoundError:
                        console.print(
                            "[yellow]Warning: bb_hg_presubmit command not found[/yellow]"
                        )
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: Error running bb_hg_presubmit: {str(e)}[/yellow]"
                        )

                    # Update STATUS to "Running TAP Tests"
                    success, _, error_msg = transition_changespec_status(
                        changespec.file_path,
                        changespec.name,
                        "Running TAP Tests",
                        validate=True,
                    )
                    if not success:
                        console.print(
                            f"[yellow]Warning: Could not update status to 'Running TAP Tests': {error_msg}[/yellow]"
                        )
                else:
                    console.print(
                        "[red]Tests failed - updating status to 'Failed to Fix Tests'[/red]"
                    )
                    # Update STATUS to "Failed to Fix Tests"
                    success, _, error_msg = transition_changespec_status(
                        changespec.file_path,
                        changespec.name,
                        "Failed to Fix Tests",
                        validate=True,
                    )
                    if not success:
                        console.print(f"[red]Error updating status: {error_msg}[/red]")

            except Exception as e:
                console.print(f"[red]Error running tests: {str(e)}[/red]")
                # Update STATUS to "Failed to Fix Tests"
                transition_changespec_status(
                    changespec.file_path,
                    changespec.name,
                    "Failed to Fix Tests",
                    validate=True,
                )
        else:
            console.print("[red]Workflow failed - reverting status[/red]")

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Workflow interrupted (Ctrl+C) - reverting status[/yellow]"
        )
        workflow_succeeded = False
    except Exception as e:
        console.print(f"[red]Workflow crashed: {str(e)} - reverting status[/red]")
        workflow_succeeded = False
    finally:
        # Revert status to "TDD CL Created" if workflow didn't succeed
        if not workflow_succeeded:
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "TDD CL Created",
                validate=True,
            )
            if not success:
                console.print(
                    f"[red]Critical: Failed to revert status: {error_msg}[/red]"
                )

        # Clean up temporary test output file
        try:
            if os.path.exists(test_output_file):
                os.remove(test_output_file)
        except Exception:
            pass  # Ignore cleanup errors

    return workflow_succeeded

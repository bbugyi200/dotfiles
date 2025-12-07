"""Fix tests workflow runner."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fix_tests_workflow.main import FixTestsWorkflow
from rich_utils import gemini_timer
from status_state_machine import transition_changespec_status

from ..changespec import ChangeSpec, find_all_changespecs
from ..field_updates import update_test_targets
from ..operations import (
    get_workspace_directory,
    update_to_changespec,
)
from .test_cache import check_test_cache, save_test_output


def _extract_failing_test_targets(changespec: ChangeSpec) -> list[str]:
    """Extract only test targets marked as (FAILED).

    Args:
        changespec: The ChangeSpec with test targets

    Returns:
        List of test target strings (with FAILED markers removed) that were marked as failed
    """
    if not changespec.test_targets:
        return []

    failing_targets = []
    for target in changespec.test_targets:
        if "(FAILED)" in target:
            # Remove the (FAILED) marker for use in commands
            failing_targets.append(target.replace(" (FAILED)", ""))

    return failing_targets


def _remove_failed_tags_from_test_targets(
    changespec: ChangeSpec, console: Console
) -> None:
    """Remove (FAILED) markers from test targets after successful tests.

    Args:
        changespec: The ChangeSpec with test targets to clean
        console: Rich console for output
    """
    if not changespec.test_targets:
        return

    cleaned_targets = [
        target.replace(" (FAILED)", "") for target in changespec.test_targets
    ]

    # Only update if there were changes
    if cleaned_targets != changespec.test_targets:
        console.print("[cyan]Removing (FAILED) markers from test targets...[/cyan]")
        targets_str = " ".join(cleaned_targets)
        success, error_msg = update_test_targets(
            changespec.file_path, changespec.name, targets_str
        )
        if success:
            console.print("[green]Test targets updated successfully[/green]")
        else:
            console.print(
                f"[yellow]Warning: Could not update test targets: {error_msg}[/yellow]"
            )


def run_fix_tests_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run fix-tests workflow for 'Failing Tests' status.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Determine which workspace directory to use
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    # Update to the changespec NAME (cd and bb_hg_update to the branch)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name, workspace_dir=workspace_dir
    )
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        return False

    # Use the determined workspace directory
    target_dir = workspace_dir

    # Generate test output file before running workflow
    console.print("[cyan]Checking for cached test output...[/cyan]")
    test_output_dir = os.path.join(target_dir, ".gai", "test_out")
    os.makedirs(test_output_dir, exist_ok=True)
    test_output_file = os.path.join(
        test_output_dir, f"test_output_{changespec.name}.txt"
    )
    try:
        # Extract only failing test targets
        failing_targets = _extract_failing_test_targets(changespec)
        test_targets_str = " ".join(failing_targets) if failing_targets else ""

        # Build test command - use failing test targets if available, otherwise use bb_rabbit_test default
        if test_targets_str:
            test_cmd = f"bb_rabbit_test {test_targets_str}"
        else:
            # No failing test targets - use default which runs tests for changed files
            test_cmd = "bb_rabbit_test"

        # Check cache first
        cache_result = check_test_cache(test_targets_str, target_dir, console)

        if cache_result.cache_hit and cache_result.output_content:
            # Use cached output
            console.print("[green]Using cached test output![/green]")
            with open(test_output_file, "w") as f:
                f.write(cache_result.output_content)
            console.print(f"[green]Test output saved to: {test_output_file}[/green]")
        else:
            # No cache hit - run tests
            if test_targets_str:
                console.print(
                    f"[cyan]Running only failing test targets: {test_targets_str}[/cyan]"
                )
            else:
                console.print(
                    "[cyan]Running tests to generate test output file...[/cyan]"
                )

            with gemini_timer("Running bb_rabbit_test"):
                result = subprocess.run(
                    test_cmd,
                    shell=True,
                    cwd=target_dir,
                    capture_output=True,
                    text=True,
                )

            # Write test output to file
            test_output_content = (
                f"Test command: {test_cmd}\n"
                f"Return code: {result.returncode}\n\n"
                f"=== STDOUT ===\n"
                f"{result.stdout}\n"
                f"=== STDERR ===\n"
                f"{result.stderr}"
            )
            with open(test_output_file, "w") as f:
                f.write(test_output_content)
            console.print(f"[green]Test output saved to: {test_output_file}[/green]")

            # Save to cache
            save_test_output(test_targets_str, target_dir, test_output_content, console)

    except Exception as e:
        console.print(f"[red]Error generating test output: {str(e)}[/red]")
        return False

    # Update STATUS to "Fixing Tests..."
    # Add workspace suffix if using a workspace share
    status_fixing = "Fixing Tests..."
    if workspace_suffix:
        status_fixing_with_suffix = f"{status_fixing} ({workspace_suffix})"
        console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")
    else:
        status_fixing_with_suffix = status_fixing

    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        status_fixing_with_suffix,
        validate=True,
    )
    if not success or old_status is None:
        console.print(f"[red]Error updating status: {error_msg}[/red]")
        return False

    # Track whether workflow succeeded for proper rollback
    workflow_succeeded = False

    # Save current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to target directory before running workflow
        os.chdir(target_dir)

        # Run fix-tests workflow
        # Pass test_output_file as relative path since we're now in target_dir
        test_output_file_rel = os.path.relpath(test_output_file, target_dir)
        console.print("[cyan]Running fix-tests workflow...[/cyan]")
        workflow = FixTestsWorkflow(
            test_cmd=test_cmd,
            test_output_file=test_output_file_rel,
            user_instructions_file=None,
            max_iterations=10,
            clquery=None,
            initial_research_file=None,
            context_file_directory=os.path.expanduser(
                f"~/.gai/projects/{project_basename}/context/"
            ),
        )
        workflow_succeeded = workflow.run()

        if workflow_succeeded:
            console.print("[green]Workflow completed successfully![/green]")

            # Run bb_rabbit_tests to check if the failing tests now pass
            # Use only the failing test targets
            failing_targets = _extract_failing_test_targets(changespec)
            test_targets_str = " ".join(failing_targets) if failing_targets else ""

            if test_targets_str:
                test_check_cmd = f"bb_rabbit_test {test_targets_str}"
            else:
                test_check_cmd = "bb_rabbit_test"

            console.print(f"[cyan]Running tests: {test_check_cmd}[/cyan]")
            try:
                with gemini_timer("Running bb_rabbit_test"):
                    result = subprocess.run(
                        test_check_cmd,
                        shell=True,
                        cwd=target_dir,
                        capture_output=True,
                        text=True,
                    )
                tests_passed = result.returncode == 0

                if tests_passed:
                    console.print("[green]Tests passed![/green]")

                    # Remove (FAILED) markers from test targets
                    _remove_failed_tags_from_test_targets(changespec, console)

                    # Update STATUS to "Needs Presubmit"
                    success, _, error_msg = transition_changespec_status(
                        changespec.file_path,
                        changespec.name,
                        "Needs Presubmit",
                        validate=True,
                    )
                    if not success:
                        console.print(
                            f"[yellow]Warning: Could not update status to 'Needs Presubmit': {error_msg}[/yellow]"
                        )
                else:
                    console.print(
                        f"[red]Tests failed - reverting status to '{old_status}'[/red]"
                    )
                    # Update STATUS back to previous status
                    success, _, error_msg = transition_changespec_status(
                        changespec.file_path,
                        changespec.name,
                        old_status,
                        validate=True,
                    )
                    if not success:
                        console.print(f"[red]Error updating status: {error_msg}[/red]")

            except Exception as e:
                console.print(f"[red]Error running tests: {str(e)}[/red]")
                # Update STATUS back to previous status
                transition_changespec_status(
                    changespec.file_path,
                    changespec.name,
                    old_status,
                    validate=True,
                )
        else:
            console.print(
                f"[red]Workflow failed - reverting status to '{old_status}'[/red]"
            )

    except KeyboardInterrupt:
        console.print(
            f"\n[yellow]Workflow interrupted (Ctrl+C) - reverting status to '{old_status}'[/yellow]"
        )
        workflow_succeeded = False
    except Exception as e:
        console.print(
            f"[red]Workflow crashed: {str(e)} - reverting status to '{old_status}'[/red]"
        )
        workflow_succeeded = False
    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Revert status to previous status if workflow didn't succeed
        if not workflow_succeeded:
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                old_status,
                validate=True,
            )
            if not success:
                console.print(
                    f"[red]Critical: Failed to revert status to '{old_status}': {error_msg}[/red]"
                )

    return workflow_succeeded

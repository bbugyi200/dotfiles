"""Fix tests workflow runner."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fix_tests_workflow.main import FixTestsWorkflow
from rich_utils import gemini_timer
from running_field import (
    claim_workspace,
    get_first_available_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from shared_utils import (
    execute_change_action,
    generate_workflow_tag,
    prompt_for_change_action,
)

from ..changespec import ChangeSpec
from ..field_updates import remove_failed_markers_from_test_targets
from ..operations import update_to_changespec
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

    # Check if there are any FAILED markers to remove
    has_failed_markers = any("(FAILED)" in target for target in changespec.test_targets)
    if not has_failed_markers:
        return

    console.print("[cyan]Removing (FAILED) markers from test targets...[/cyan]")
    success, error_msg = remove_failed_markers_from_test_targets(
        changespec.file_path, changespec.name
    )
    if success:
        console.print("[green]Test targets updated successfully[/green]")
    else:
        console.print(
            f"[yellow]Warning: Could not update test targets: {error_msg}[/yellow]"
        )


def run_fix_tests_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run fix-tests workflow for ChangeSpecs with failing test targets.

    This workflow does NOT change the STATUS field. It runs the fix-tests
    workflow and removes (FAILED) markers from test targets on success.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Find first available workspace and claim it
    workspace_num = get_first_available_workspace(
        changespec.file_path, project_basename
    )
    workspace_dir, workspace_suffix = get_workspace_directory_for_num(
        workspace_num, project_basename
    )

    # Claim the workspace FIRST to reserve it before doing any work
    claim_success = claim_workspace(
        changespec.file_path,
        workspace_num,
        "fix-tests",
        changespec.name,
    )
    if not claim_success:
        console.print("[red]Error: Failed to claim workspace[/red]")
        return False

    # Use the determined workspace directory
    target_dir = workspace_dir

    if workspace_suffix:
        console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    # Update to the changespec NAME (cd and bb_hg_update to the branch)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name, workspace_dir=workspace_dir
    )
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        # Release workspace since we failed before running the workflow
        release_workspace(
            changespec.file_path, workspace_num, "fix-tests", changespec.name
        )
        return False

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

    # Track whether workflow succeeded
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

                    # Prompt user for action on changes
                    prompt_result = prompt_for_change_action(console, target_dir)
                    if prompt_result is None:
                        console.print(
                            "\n[yellow]Warning: No changes detected.[/yellow]"
                        )
                        workflow_succeeded = False
                        return False

                    action, action_args = prompt_result

                    # Handle reject
                    if action == "reject":
                        console.print(
                            "[yellow]Changes rejected. Returning to view.[/yellow]"
                        )
                        workflow_succeeded = False
                        return False

                    # Handle purge
                    if action == "purge":
                        execute_change_action(
                            action=action,
                            action_args=action_args,
                            console=console,
                            target_dir=target_dir,
                        )
                        workflow_succeeded = False
                        return False

                    # Generate workflow tag for amend
                    workflow_tag = generate_workflow_tag()

                    # Execute the action (amend or commit)
                    action_success = execute_change_action(
                        action=action,
                        action_args=action_args,
                        console=console,
                        target_dir=target_dir,
                        workflow_tag=workflow_tag,
                        workflow_name="fix-tests",
                    )

                    if not action_success:
                        workflow_succeeded = False
                        return False

                    # Remove (FAILED) markers from test targets
                    _remove_failed_tags_from_test_targets(changespec, console)
                else:
                    console.print("[red]Tests still failing[/red]")
                    workflow_succeeded = False

            except Exception as e:
                console.print(f"[red]Error running tests: {str(e)}[/red]")
                workflow_succeeded = False
        else:
            console.print("[red]Workflow failed[/red]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Workflow interrupted (Ctrl+C)[/yellow]")
        workflow_succeeded = False
    except Exception as e:
        console.print(f"[red]Workflow crashed: {str(e)}[/red]")
        workflow_succeeded = False
    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Always release the workspace when done
        release_workspace(
            changespec.file_path, workspace_num, "fix-tests", changespec.name
        )

    return workflow_succeeded

"""Fix tests workflow runner."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from change_actions import (
    execute_change_action,
    prompt_for_change_action,
)
from fix_tests_workflow.main import FixTestsWorkflow
from rich_utils import gemini_timer
from running_field import (
    claim_workspace,
    get_first_available_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)

from ..changespec import ChangeSpec
from ..hooks import (
    clear_failed_test_target_hook_status,
    get_failing_test_target_hooks,
    get_test_target_from_hook,
)
from ..operations import update_to_changespec
from .test_cache import check_test_cache, save_test_output


def _extract_failing_test_targets(changespec: ChangeSpec) -> list[str]:
    """Extract test targets from hooks with FAILED status.

    Args:
        changespec: The ChangeSpec with hooks

    Returns:
        List of test target strings from hooks that have FAILED status
    """
    if not changespec.hooks:
        return []

    failing_hooks = get_failing_test_target_hooks(changespec.hooks)
    failing_targets = []
    for hook in failing_hooks:
        target = get_test_target_from_hook(hook)
        if target:
            failing_targets.append(target)

    return failing_targets


def _clear_failed_test_target_hooks(changespec: ChangeSpec, console: Console) -> None:
    """Clear the FAILED status from test target hooks after successful tests.

    Args:
        changespec: The ChangeSpec with hooks to update
        console: Rich console for output
    """
    if not changespec.hooks:
        return

    # Check if there are any failed test target hooks
    failing_hooks = get_failing_test_target_hooks(changespec.hooks)
    if not failing_hooks:
        return

    console.print("[cyan]Clearing FAILED status from test target hooks...[/cyan]")
    success = clear_failed_test_target_hook_status(
        changespec.file_path, changespec.name, changespec.hooks
    )
    if success:
        console.print("[green]Test target hooks updated successfully[/green]")
    else:
        console.print("[yellow]Warning: Could not update test target hooks[/yellow]")


def run_fix_tests_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run fix-tests workflow for ChangeSpecs with failing test target hooks.

    This workflow does NOT change the STATUS field. It runs the fix-tests
    workflow and clears FAILED status from test target hooks on success.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Find first available workspace and claim it
    workspace_num = get_first_available_workspace(changespec.file_path)
    workspace_dir, workspace_suffix = get_workspace_directory_for_num(
        workspace_num, changespec.project_basename
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
                f"~/.gai/projects/{changespec.project_basename}/context/"
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

                    # Determine chat_path from workflow artifacts (use log.md)
                    chat_path = None
                    if workflow.artifacts_dir:
                        log_path = os.path.join(workflow.artifacts_dir, "log.md")
                        if os.path.exists(log_path):
                            chat_path = log_path

                    # Prompt user for action on changes (creates proposal first)
                    prompt_result = prompt_for_change_action(
                        console,
                        target_dir,
                        workflow_name="fix-tests",
                        chat_path=chat_path,
                    )
                    if prompt_result is None:
                        console.print(
                            "\n[yellow]Warning: No changes detected.[/yellow]"
                        )
                        workflow_succeeded = False
                        return False

                    action, action_args = prompt_result

                    # Handle reject (proposal stays in HISTORY)
                    if action == "reject":
                        console.print(
                            "[yellow]Changes rejected. Proposal saved.[/yellow]"
                        )
                        workflow_succeeded = False
                        return False

                    # Handle purge (delete proposal)
                    if action == "purge":
                        execute_change_action(
                            action=action,
                            action_args=action_args,
                            console=console,
                            target_dir=target_dir,
                        )
                        workflow_succeeded = False
                        return False

                    # Execute accept action
                    action_success = execute_change_action(
                        action=action,
                        action_args=action_args,
                        console=console,
                        target_dir=target_dir,
                    )

                    if not action_success:
                        workflow_succeeded = False
                        return False

                    # Remove (FAILED) markers from test targets
                    _clear_failed_test_target_hooks(changespec, console)
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

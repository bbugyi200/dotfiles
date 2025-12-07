"""TDD feature workflow runner."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from new_tdd_feature_workflow.main import NewTddFeatureWorkflow
from rich_utils import gemini_timer
from shared_utils import generate_workflow_tag, safe_hg_amend
from status_state_machine import transition_changespec_status

from ..changespec import ChangeSpec, find_all_changespecs
from ..commit_ops import run_bb_hg_upload
from ..operations import (
    get_workspace_directory,
    update_to_changespec,
)
from .test_cache import check_test_cache, save_test_output


# Import the helper function from workflow_ops
def _remove_failed_tags_from_test_targets(
    changespec: ChangeSpec, console: Console
) -> None:
    """Remove (FAILED) markers from test targets after successful tests.

    Args:
        changespec: The ChangeSpec with test targets to clean
        console: Rich console for output
    """
    from ..field_updates import update_test_targets

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


def run_tdd_feature_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run new-tdd-feature workflow for 'TDD CL Created' status.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Note: We no longer validate test_targets here - the agent will figure out
    # the appropriate test command from the test output file

    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Set design docs directory to ~/.gai/projects/<project>/context/
    design_docs_dir = os.path.expanduser(f"~/.gai/projects/{project_basename}/context/")

    # Determine which workspace directory to use
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    # Update to the changespec NAME (cd and bb_hg_update to the TDD CL branch)
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
        # Convert test_targets list to space-separated string, removing (FAILED) markers
        test_targets_str = (
            " ".join(
                target.replace(" (FAILED)", "") for target in changespec.test_targets
            )
            if changespec.test_targets
            else ""
        )

        # Build test command - use test targets if available, otherwise use bb_rabbit_test default
        if test_targets_str:
            test_cmd = f"bb_rabbit_test {test_targets_str}"
        else:
            # No test targets specified - use default which runs tests for changed files
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
            console.print("[cyan]Running tests to generate test output file...[/cyan]")

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

    # Update STATUS to "Finishing TDD CL..."
    # Add workspace suffix if using a workspace share
    status_finishing = "Finishing TDD CL..."
    if workspace_suffix:
        status_finishing_with_suffix = f"{status_finishing} ({workspace_suffix})"
        console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")
    else:
        status_finishing_with_suffix = status_finishing

    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        status_finishing_with_suffix,
        validate=True,
    )
    if not success:
        console.print(f"[red]Error updating status: {error_msg}[/red]")
        return False

    # Track whether workflow succeeded for proper rollback
    workflow_succeeded = False

    # Save current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to target directory before running workflow
        os.chdir(target_dir)

        # Run new-tdd-feature workflow
        # Pass test_output_file as relative path since we're now in target_dir
        test_output_file_rel = os.path.relpath(test_output_file, target_dir)
        console.print("[cyan]Running new-tdd-feature workflow...[/cyan]")
        workflow = NewTddFeatureWorkflow(
            test_output_file=test_output_file_rel,
            user_instructions_file=None,
            max_iterations=10,
            context_file_directory=design_docs_dir,
        )
        workflow_succeeded = workflow.run()

        if workflow_succeeded:
            console.print("[green]Workflow completed successfully![/green]")

            # Run bb_rabbit_tests to check if tests pass
            # Use the test targets if available, otherwise use default (remove FAILED markers)
            test_targets_str = (
                " ".join(
                    target.replace(" (FAILED)", "")
                    for target in changespec.test_targets
                )
                if changespec.test_targets
                else ""
            )
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

                    # Amend the commit with the workflow's changes before uploading
                    workflow_tag = generate_workflow_tag()
                    commit_note = f"@AI({workflow_tag}) [new-tdd-feature]"
                    console.print(
                        "[cyan]Amending commit with workflow changes...[/cyan]"
                    )
                    amend_successful = safe_hg_amend(
                        commit_note, use_unamend_first=False
                    )
                    if not amend_successful:
                        console.print(
                            "[yellow]Warning: hg amend failed - skipping upload to Critique[/yellow]"
                        )
                    else:
                        # Upload to Critique (treat as warning if it fails)
                        success, error_msg = run_bb_hg_upload(target_dir, console)
                        if not success:
                            console.print(f"[yellow]Warning: {error_msg}[/yellow]")

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
                        "[red]Tests failed - updating status to 'Failing Tests'[/red]"
                    )
                    # Update STATUS to "Failing Tests"
                    success, _, error_msg = transition_changespec_status(
                        changespec.file_path,
                        changespec.name,
                        "Failing Tests",
                        validate=True,
                    )
                    if not success:
                        console.print(f"[red]Error updating status: {error_msg}[/red]")

            except Exception as e:
                console.print(f"[red]Error running tests: {str(e)}[/red]")
                # Update STATUS to "Failing Tests"
                transition_changespec_status(
                    changespec.file_path,
                    changespec.name,
                    "Failing Tests",
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
        # Restore original directory
        os.chdir(original_dir)

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

    return workflow_succeeded

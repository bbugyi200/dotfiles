"""Workflow-specific operations for ChangeSpecs."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from crs_workflow import CrsWorkflow
from fix_tests_workflow.main import FixTestsWorkflow
from new_tdd_feature_workflow.main import NewTddFeatureWorkflow
from qa_workflow import QaWorkflow
from shared_utils import generate_workflow_tag
from status_state_machine import transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs
from .field_updates import update_tap_field_from_cl
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
    # Note: We no longer validate test_targets here - the agent will figure out
    # the appropriate test command from the test output file

    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Set design docs directory to ~/.gai/context/<project>
    design_docs_dir = os.path.expanduser(f"~/.gai/context/{project_basename}")

    # Update to the changespec NAME (cd and bb_hg_update to the TDD CL branch)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name
    )
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
    test_output_dir = os.path.join(target_dir, ".gai", "test_out")
    os.makedirs(test_output_dir, exist_ok=True)
    test_output_file = os.path.join(
        test_output_dir, f"test_output_{changespec.name}.txt"
    )
    try:
        # Convert test_targets list to space-separated string
        test_targets_str = (
            " ".join(changespec.test_targets) if changespec.test_targets else ""
        )

        # Build test command - use test targets if available, otherwise use bb_rabbit_test default
        if test_targets_str:
            test_cmd = f"bb_rabbit_test {test_targets_str}"
        else:
            # No test targets specified - use default which runs tests for changed files
            test_cmd = "bb_rabbit_test"

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

    # Update STATUS to "Finishing TDD CL..."
    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        "Finishing TDD CL...",
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
            # Use the test targets if available, otherwise use default
            test_targets_str = (
                " ".join(changespec.test_targets) if changespec.test_targets else ""
            )
            if test_targets_str:
                test_check_cmd = f"bb_rabbit_test {test_targets_str}"
            else:
                test_check_cmd = "bb_rabbit_test"

            console.print(f"[cyan]Running tests: {test_check_cmd}[/cyan]")
            try:
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

                    # Run bb_hg_presubmit
                    console.print("[cyan]Running bb_hg_presubmit...[/cyan]")
                    try:
                        subprocess.run(
                            ["bb_hg_presubmit"],
                            cwd=target_dir,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        console.print(
                            "[green]bb_hg_presubmit completed successfully![/green]"
                        )
                        # Construct and store TAP URL from CL field
                        success, error_msg = update_tap_field_from_cl(
                            changespec.file_path, changespec.name
                        )
                        if success:
                            console.print("[green]TAP URL saved from CL field[/green]")
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


def run_qa_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run qa workflow for 'Ready for QA' status.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Update to the changespec NAME (cd and bb_hg_update to the CL being QA'd)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name
    )
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        return False

    # Get target directory for running workflow
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
    # These should be set since update_to_changespec already validated them
    assert goog_cloud_dir is not None
    assert goog_src_dir_base is not None
    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Copy context files from ~/.gai/context/<project> to target_dir/.gai/context/<project>
    source_context_dir = os.path.expanduser(f"~/.gai/context/{project_basename}")
    target_context_dir = os.path.join(target_dir, ".gai", "context", project_basename)

    if os.path.exists(source_context_dir) and os.path.isdir(source_context_dir):
        import shutil

        os.makedirs(os.path.dirname(target_context_dir), exist_ok=True)
        if os.path.exists(target_context_dir):
            shutil.rmtree(target_context_dir)
        shutil.copytree(source_context_dir, target_context_dir)

    # Set context file directory to the copied location
    context_file_directory = (
        target_context_dir if os.path.exists(target_context_dir) else None
    )

    # Update STATUS to "Running QA..."
    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        "Running QA...",
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

        # Run the QA workflow
        console.print("[cyan]Running qa workflow...[/cyan]")
        workflow = QaWorkflow(context_file_directory=context_file_directory)
        workflow_succeeded = workflow.run()

        if workflow_succeeded:
            # Update STATUS to "Pre-Mailed"
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Pre-Mailed",
                validate=True,
            )
            if success:
                console.print("[green]QA workflow completed successfully![/green]")
            else:
                console.print(
                    f"[yellow]Warning: Could not update status to 'Pre-Mailed': {error_msg}[/yellow]"
                )
        else:
            console.print("[red]QA workflow failed - reverting status[/red]")

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]QA workflow interrupted (Ctrl+C) - reverting status[/yellow]"
        )
        workflow_succeeded = False
    except Exception as e:
        console.print(f"[red]QA workflow crashed: {str(e)} - reverting status[/red]")
        workflow_succeeded = False
    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Revert status to "Ready for QA" if workflow didn't succeed
        if not workflow_succeeded:
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Ready for QA",
                validate=True,
            )
            if not success:
                console.print(
                    f"[red]Critical: Failed to revert status: {error_msg}[/red]"
                )

    return workflow_succeeded


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

    # Update to the changespec NAME (cd and bb_hg_update to the branch)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name
    )
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
    test_output_dir = os.path.join(target_dir, ".gai", "test_out")
    os.makedirs(test_output_dir, exist_ok=True)
    test_output_file = os.path.join(
        test_output_dir, f"test_output_{changespec.name}.txt"
    )
    try:
        # Convert test_targets list to space-separated string
        test_targets_str = (
            " ".join(changespec.test_targets) if changespec.test_targets else ""
        )

        # Build test command - use test targets if available, otherwise use bb_rabbit_test default
        if test_targets_str:
            test_cmd = f"bb_rabbit_test {test_targets_str}"
        else:
            # No test targets specified - use default which runs tests for changed files
            test_cmd = "bb_rabbit_test"

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

    # Update STATUS to "Fixing Tests..."
    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        "Fixing Tests...",
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
                f"~/.gai/context/{project_basename}"
            ),
        )
        workflow_succeeded = workflow.run()

        if workflow_succeeded:
            console.print("[green]Workflow completed successfully![/green]")

            # Run bb_rabbit_tests to check if tests pass
            # Use the test targets if available, otherwise use default
            test_targets_str = (
                " ".join(changespec.test_targets) if changespec.test_targets else ""
            )
            if test_targets_str:
                test_check_cmd = f"bb_rabbit_test {test_targets_str}"
            else:
                test_check_cmd = "bb_rabbit_test"

            console.print(f"[cyan]Running tests: {test_check_cmd}[/cyan]")
            try:
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

                    # Run bb_hg_presubmit
                    console.print("[cyan]Running bb_hg_presubmit...[/cyan]")
                    try:
                        subprocess.run(
                            ["bb_hg_presubmit"],
                            cwd=target_dir,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        console.print(
                            "[green]bb_hg_presubmit completed successfully![/green]"
                        )
                        # Construct and store TAP URL from CL field
                        success, error_msg = update_tap_field_from_cl(
                            changespec.file_path, changespec.name
                        )
                        if success:
                            console.print("[green]TAP URL saved from CL field[/green]")
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
                        "[red]Tests failed - keeping status at 'Failing Tests'[/red]"
                    )
                    # Update STATUS back to "Failing Tests"
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

        # Revert status to "Failing Tests" if workflow didn't succeed
        if not workflow_succeeded:
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Failing Tests",
                validate=True,
            )
            if not success:
                console.print(
                    f"[red]Critical: Failed to revert status: {error_msg}[/red]"
                )

    return workflow_succeeded


def run_crs_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run crs workflow for 'Mailed' status.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Update to the changespec NAME (cd and bb_hg_update to the branch)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name
    )
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        return False

    # Get target directory
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
    # These should be set since update_to_changespec already validated them
    assert goog_cloud_dir is not None
    assert goog_src_dir_base is not None
    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Save current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to target directory BEFORE setting up context
        # (this ensures relative paths are calculated correctly)
        os.chdir(target_dir)

        # Set context file directory to ~/.gai/context/<project>
        # and convert to relative path from current directory
        context_file_directory_abs = os.path.expanduser(
            f"~/.gai/context/{project_basename}"
        )
        if os.path.isdir(context_file_directory_abs):
            context_file_directory = os.path.relpath(context_file_directory_abs)
        else:
            context_file_directory = None

        # Run the CRS workflow
        console.print("[cyan]Running CRS workflow...[/cyan]")
        workflow = CrsWorkflow(context_file_directory=context_file_directory)
        workflow_succeeded = workflow.run()

        if not workflow_succeeded:
            console.print("[red]CRS workflow failed[/red]")
            return False

        # Show diff with color
        console.print("\n[cyan]Showing changes from CRS workflow...[/cyan]\n")
        try:
            subprocess.run(
                ["hg", "diff", "--color=always"],
                cwd=target_dir,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]hg diff failed (exit code {e.returncode})[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]hg command not found[/red]")
            return False

        # Prompt user for action
        console.print(
            "\n[cyan]Accept changes (y), reject changes (n), or purge changes (x)?[/cyan] ",
            end="",
        )
        user_input = input().strip().lower()

        if user_input == "y":
            # Generate workflow tag for the commit message
            workflow_tag = generate_workflow_tag()

            # Amend the commit with AI tag
            console.print("[cyan]Amending commit with AI tag...[/cyan]")
            try:
                subprocess.run(
                    ["hg", "amend", "-n", f"@AI({workflow_tag}) [crs]"],
                    cwd=target_dir,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]hg amend failed (exit code {e.returncode})[/red]")
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                return False

            # Upload to Critique
            console.print("[cyan]Uploading to Critique...[/cyan]")
            try:
                subprocess.run(
                    ["hg", "upload", "tree"],
                    cwd=target_dir,
                    check=True,
                )
                console.print("[green]CRS workflow completed successfully![/green]")
                return True
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[red]hg upload tree failed (exit code {e.returncode})[/red]"
                )
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                return False

        elif user_input == "n":
            # Reject changes - just return
            console.print(
                "[yellow]Changes rejected. Returning to ChangeSpec view.[/yellow]"
            )
            return False

        elif user_input == "x":
            # Purge changes
            console.print("[cyan]Purging changes...[/cyan]")
            try:
                subprocess.run(
                    ["hg", "update", "--clean", "."],
                    cwd=target_dir,
                    check=True,
                )
                console.print("[green]Changes purged successfully.[/green]")
                return False
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[red]hg update --clean failed (exit code {e.returncode})[/red]"
                )
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                return False

        else:
            console.print(f"[red]Invalid option: {user_input}[/red]")
            return False

    finally:
        # Restore original directory
        os.chdir(original_dir)

"""Main workflow for the work subcommand."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from new_ez_feature_workflow.main import NewEzFeatureWorkflow
from new_failing_tests_workflow.main import NewFailingTestWorkflow
from status_state_machine import transition_changespec_status
from workflow_base import BaseWorkflow

from .changespec import ChangeSpec, display_changespec, find_all_changespecs
from .commit_ops import run_bb_hg_commit_and_update_cl
from .field_updates import (
    update_tap_field_from_cl,
    update_test_targets,
)
from .filters import filter_changespecs, validate_filters
from .mail_ops import handle_mail
from .operations import (
    extract_changespec_text,
    should_show_run_option,
    update_to_changespec,
)
from .status import prompt_status_change
from .workflow_ops import (
    run_fix_tests_workflow,
    run_qa_workflow,
    run_tdd_feature_workflow,
    unblock_child_changespecs,
)


class WorkWorkflow(BaseWorkflow):
    """Interactive workflow for navigating through ChangeSpecs."""

    def __init__(
        self,
        status_filters: list[str] | None = None,
        project_filters: list[str] | None = None,
        model_size_override: str | None = None,
    ) -> None:
        """Initialize the work workflow.

        Args:
            status_filters: List of status values to filter by (OR logic)
            project_filters: List of project basenames to filter by (OR logic)
            model_size_override: Override model size for all GeminiCommandWrapper instances
        """
        self.console = Console()
        self.status_filters = status_filters
        self.project_filters = project_filters

        # Set global model size override in environment if specified
        if model_size_override:
            os.environ["GAI_MODEL_SIZE_OVERRIDE"] = model_size_override

    @property
    def name(self) -> str:
        """Return the name of this workflow."""
        return "work"

    @property
    def description(self) -> str:
        """Return a description of what this workflow does."""
        return "Interactively navigate through all ChangeSpecs in project files"

    def _is_in_tmux(self) -> bool:
        """Check if currently running inside a tmux session.

        Returns:
            True if running inside tmux, False otherwise
        """
        return "TMUX" in os.environ

    def _reload_and_reposition(
        self, changespecs: list[ChangeSpec], current_changespec: ChangeSpec
    ) -> tuple[list[ChangeSpec], int]:
        """Reload changespecs and try to stay on the same one.

        Args:
            changespecs: Current list of changespecs (unused, will be reloaded)
            current_changespec: The changespec we're currently viewing

        Returns:
            Tuple of (new_changespecs_list, new_index)
        """
        new_changespecs = find_all_changespecs()
        new_changespecs = filter_changespecs(
            new_changespecs, self.status_filters, self.project_filters
        )

        # Try to find the same changespec by name
        new_idx = 0
        for idx, cs in enumerate(new_changespecs):
            if cs.name == current_changespec.name:
                new_idx = idx
                break

        return new_changespecs, new_idx

    def _handle_next(
        self, current_idx: int, max_idx: int
    ) -> tuple[int, str] | tuple[None, None]:
        """Handle 'n' (next) navigation.

        Args:
            current_idx: Current index in changespecs list
            max_idx: Maximum valid index

        Returns:
            Tuple of (new_index, new_direction) or (None, None) if can't move
        """
        if current_idx < max_idx:
            return current_idx + 1, "n"
        else:
            self.console.print("[yellow]Already at last ChangeSpec[/yellow]")
            return None, None

    def _handle_prev(self, current_idx: int) -> tuple[int, str] | tuple[None, None]:
        """Handle 'p' (prev) navigation.

        Args:
            current_idx: Current index in changespecs list

        Returns:
            Tuple of (new_index, new_direction) or (None, None) if can't move
        """
        if current_idx > 0:
            return current_idx - 1, "p"
        else:
            self.console.print("[yellow]Already at first ChangeSpec[/yellow]")
            return None, None

    def _handle_status_change(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle 's' (status change) action.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        if changespec.status in ["Blocked (EZ)", "Blocked (TDD)"]:
            self.console.print(
                "[yellow]Cannot change status of blocked ChangeSpec[/yellow]"
            )
            return changespecs, current_idx

        new_status = prompt_status_change(self.console, changespec.status)
        if new_status:
            # Update the status in the project file
            success, old_status, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                new_status,
                validate=False,  # Don't validate - allow any transition
            )
            if success:
                self.console.print(
                    f"[green]Status updated: {old_status} → {new_status}[/green]"
                )

                # If status changed to Pre-Mailed, unblock child ChangeSpecs
                if new_status == "Pre-Mailed":
                    unblocked_count = unblock_child_changespecs(
                        changespec, self.console
                    )
                    if unblocked_count > 0:
                        self.console.print(
                            f"[green]Unblocked {unblocked_count} child ChangeSpec(s)[/green]"
                        )

                # Reload changespecs to reflect the update
                changespecs, current_idx = self._reload_and_reposition(
                    changespecs, changespec
                )
            else:
                self.console.print(f"[red]Error: {error_msg}[/red]")

        return changespecs, current_idx

    def _handle_run_workflow(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle 'r' (run workflow) action.

        Runs workflow based on STATUS:
        - "Unstarted (EZ)": Runs new-ez-feature workflow
        - "Unstarted (TDD)": Runs new-failing-tests workflow
        - "TDD CL Created": Runs new-tdd-feature workflow

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        if not should_show_run_option(changespec):
            self.console.print(
                "[yellow]Run option not available for this ChangeSpec[/yellow]"
            )
            return changespecs, current_idx

        # Special handling for "TDD CL Created" status (new-tdd-feature workflow)
        if changespec.status == "TDD CL Created":
            return self._handle_run_tdd_feature_workflow(
                changespec, changespecs, current_idx
            )

        # Special handling for "Ready for QA" status (qa workflow)
        if changespec.status == "Ready for QA":
            return self._handle_run_qa_workflow(changespec, changespecs, current_idx)

        # Special handling for "Failing Tests" status (fix-tests workflow)
        if changespec.status == "Failing Tests":
            return self._handle_run_fix_tests_workflow(
                changespec, changespecs, current_idx
            )

        # Determine which workflow to run based on STATUS
        is_tdd_workflow = changespec.status == "Unstarted (TDD)"

        # Extract project basename and changespec text
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
        changespec_text = extract_changespec_text(
            changespec.file_path, changespec.name, self.console
        )

        if not changespec_text:
            self.console.print("[red]Error: Could not extract ChangeSpec text[/red]")
            return changespecs, current_idx

        # Update to the changespec (cd and bb_hg_update)
        success, error_msg = update_to_changespec(changespec, self.console)
        if not success:
            self.console.print(f"[red]Error: {error_msg}[/red]")
            return changespecs, current_idx

        # Get target directory for running workflow
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
        # These should be set since update_to_changespec already validated them
        assert goog_cloud_dir is not None
        assert goog_src_dir_base is not None
        target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

        # Set design docs directory to ~/.gai/context/<project>
        design_docs_dir = os.path.expanduser(f"~/.gai/context/{project_basename}")

        # Update STATUS based on workflow type
        if is_tdd_workflow:
            status_creating = "Creating TDD CL..."
            status_final = "TDD CL Created"
            workflow_name = "new-failing-tests"
        else:
            status_creating = "Creating EZ CL..."
            status_final = "Running TAP Tests"
            workflow_name = "new-ez-feature"

        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            status_creating,
            validate=True,
        )
        if not success:
            self.console.print(f"[red]Error updating status: {error_msg}[/red]")
            return changespecs, current_idx

        # Track whether workflow succeeded for proper rollback
        workflow_succeeded = False

        # Save current directory to restore later
        original_dir = os.getcwd()

        try:
            # Change to target directory before running workflow
            os.chdir(target_dir)

            # Run the appropriate workflow
            self.console.print(f"[cyan]Running {workflow_name} workflow...[/cyan]")
            workflow: BaseWorkflow
            if is_tdd_workflow:
                workflow = NewFailingTestWorkflow(
                    project_name=project_basename,
                    changespec_text=changespec_text,
                    context_file_directory=design_docs_dir,
                )
            else:
                workflow = NewEzFeatureWorkflow(
                    project_name=project_basename,
                    design_docs_dir=design_docs_dir,
                    changespec_text=changespec_text,
                    context_file_directory=design_docs_dir,
                )
            workflow_succeeded = workflow.run()

            if workflow_succeeded:
                # Run bb_hg_commit to create commit and update CL field
                self.console.print(
                    "[cyan]Creating Mercurial commit with bb_hg_commit...[/cyan]"
                )
                success, error_msg = run_bb_hg_commit_and_update_cl(
                    changespec, self.console
                )
                if not success:
                    self.console.print(
                        f"[red]Error: Failed to create commit: {error_msg}[/red]"
                    )
                    # Fail the workflow and trigger status rollback
                    workflow_succeeded = False

            if workflow_succeeded:
                # Update TEST TARGETS field for TDD workflow
                if is_tdd_workflow:
                    # Extract test_targets from workflow final state
                    if hasattr(workflow, "final_state") and workflow.final_state:
                        test_targets = workflow.final_state.get("test_targets")
                        if test_targets and isinstance(test_targets, str):
                            self.console.print(
                                f"[cyan]Updating TEST TARGETS field with: {test_targets}[/cyan]"
                            )
                            success, error_msg = update_test_targets(
                                changespec.file_path, changespec.name, test_targets
                            )
                            if not success:
                                self.console.print(
                                    f"[yellow]Warning: Failed to update TEST TARGETS: {error_msg}[/yellow]"
                                )
                            else:
                                self.console.print(
                                    "[green]TEST TARGETS field updated successfully![/green]"
                                )
                        else:
                            self.console.print(
                                "[yellow]Warning: Workflow did not provide test_targets to update[/yellow]"
                            )

                # Run bb_hg_presubmit for new-ez-feature workflow
                if not is_tdd_workflow:
                    self.console.print("[cyan]Running bb_hg_presubmit...[/cyan]")
                    try:
                        subprocess.run(
                            ["bb_hg_presubmit"],
                            cwd=target_dir,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        # Construct and store TAP URL from CL field
                        success, error_msg = update_tap_field_from_cl(
                            changespec.file_path, changespec.name
                        )
                        if success:
                            self.console.print(
                                "[green]TAP URL saved from CL field[/green]"
                            )
                        else:
                            self.console.print(
                                f"[yellow]Warning: Could not save TAP URL: {error_msg}[/yellow]"
                            )
                    except subprocess.CalledProcessError as e:
                        self.console.print(
                            f"[yellow]Warning: bb_hg_presubmit failed (exit code {e.returncode})[/yellow]"
                        )
                    except FileNotFoundError:
                        self.console.print(
                            "[yellow]Warning: bb_hg_presubmit command not found[/yellow]"
                        )
                    except Exception as e:
                        self.console.print(
                            f"[yellow]Warning: Error running bb_hg_presubmit: {str(e)}[/yellow]"
                        )

                # Update STATUS to final status
                success, _, error_msg = transition_changespec_status(
                    changespec.file_path,
                    changespec.name,
                    status_final,
                    validate=True,
                )
                if success:
                    self.console.print(
                        "[green]Workflow completed successfully![/green]"
                    )
                else:
                    self.console.print(
                        f"[yellow]Warning: Could not update status to '{status_final}': {error_msg}[/yellow]"
                    )
            else:
                self.console.print("[red]Workflow failed - reverting status[/red]")

        except KeyboardInterrupt:
            self.console.print(
                "\n[yellow]Workflow interrupted (Ctrl+C) - reverting status[/yellow]"
            )
            workflow_succeeded = False
        except Exception as e:
            self.console.print(
                f"[red]Workflow crashed: {str(e)} - reverting status[/red]"
            )
            workflow_succeeded = False
        finally:
            # Restore original directory
            os.chdir(original_dir)

            # Revert status to appropriate "Unstarted" variant if workflow didn't succeed
            if not workflow_succeeded:
                revert_status = (
                    "Unstarted (TDD)" if is_tdd_workflow else "Unstarted (EZ)"
                )
                success, _, error_msg = transition_changespec_status(
                    changespec.file_path,
                    changespec.name,
                    revert_status,
                    validate=True,
                )
                if not success:
                    self.console.print(
                        f"[red]Critical: Failed to revert status: {error_msg}[/red]"
                    )

            # Reload changespecs to reflect updates
            changespecs, current_idx = self._reload_and_reposition(
                changespecs, changespec
            )

        return changespecs, current_idx

    def _handle_run_tdd_feature_workflow(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle running new-tdd-feature workflow for 'TDD CL Created' status.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        # Run the workflow (handles all logic including status transitions)
        run_tdd_feature_workflow(changespec, self.console)

        # Reload changespecs to reflect updates
        changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

        return changespecs, current_idx

    def _handle_run_qa_workflow(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle running qa workflow for 'Ready for QA' status.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        # Run the workflow (handles all logic including status transitions)
        run_qa_workflow(changespec, self.console)

        # Reload changespecs to reflect updates
        changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

        return changespecs, current_idx

    def _handle_run_fix_tests_workflow(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle running fix-tests workflow for 'Failing Tests' status.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        # Run the workflow (handles all logic including status transitions)
        run_fix_tests_workflow(changespec, self.console)

        # Reload changespecs to reflect updates
        changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

        return changespecs, current_idx

    def _handle_show_diff(self, changespec: ChangeSpec) -> None:
        """Handle 'd' (show diff) action.

        Args:
            changespec: Current ChangeSpec
        """
        if changespec.cl is None or changespec.cl == "None":
            self.console.print("[yellow]Cannot show diff: CL is not set[/yellow]")
            return

        # Update to the changespec branch (NAME field) to show the diff
        success, error_msg = update_to_changespec(
            changespec, self.console, revision=changespec.name
        )
        if not success:
            self.console.print(f"[red]Error: {error_msg}[/red]")
            return

        # Run branch_diff
        # Get target directory for running branch_diff
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
        # These should be set since update_to_changespec already validated them
        assert goog_cloud_dir is not None
        assert goog_src_dir_base is not None
        target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

        try:
            # Run branch_diff and let it take over the terminal
            subprocess.run(
                ["branch_diff"],
                cwd=target_dir,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.console.print(
                f"[red]branch_diff failed (exit code {e.returncode})[/red]"
            )
        except FileNotFoundError:
            self.console.print("[red]branch_diff command not found[/red]")
        except Exception as e:
            self.console.print(
                f"[red]Unexpected error running branch_diff: {str(e)}[/red]"
            )

    def _handle_create_tmux(self, changespec: ChangeSpec) -> None:
        """Handle 't' (create tmux window) action.

        Args:
            changespec: Current ChangeSpec
        """
        if changespec.cl is None or changespec.cl == "None":
            self.console.print(
                "[yellow]Cannot create tmux window: CL is not set[/yellow]"
            )
            return

        if not self._is_in_tmux():
            self.console.print(
                "[yellow]Cannot create tmux window: not in tmux session[/yellow]"
            )
            return

        # Extract project basename
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

        # Get required environment variables
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

        if not goog_cloud_dir:
            self.console.print(
                "[red]Error: GOOG_CLOUD_DIR environment variable is not set[/red]"
            )
            return
        if not goog_src_dir_base:
            self.console.print(
                "[red]Error: GOOG_SRC_DIR_BASE environment variable is not set[/red]"
            )
            return

        # Build target directory path
        target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

        # Build the command to run in the new tmux window
        # cd to the directory, run bb_hg_update, then start a shell
        tmux_cmd = f"cd {target_dir} && bb_hg_update {changespec.name} && exec $SHELL"

        try:
            # Create new tmux window with the project name
            subprocess.run(
                [
                    "tmux",
                    "new-window",
                    "-n",
                    project_basename,
                    tmux_cmd,
                ],
                check=True,
            )
            self.console.print(
                f"[green]Created tmux window '{project_basename}'[/green]"
            )
        except subprocess.CalledProcessError as e:
            self.console.print(
                f"[red]tmux command failed (exit code {e.returncode})[/red]"
            )
        except FileNotFoundError:
            self.console.print("[red]tmux command not found[/red]")
        except Exception as e:
            self.console.print(
                f"[red]Unexpected error creating tmux window: {str(e)}[/red]"
            )

    def _handle_findreviewers(self, changespec: ChangeSpec) -> None:
        """Handle 'f' (findreviewers) action.

        Args:
            changespec: Current ChangeSpec
        """
        if changespec.status != "Pre-Mailed":
            self.console.print(
                "[yellow]findreviewers option only available for Pre-Mailed ChangeSpecs[/yellow]"
            )
            return

        # Extract project basename
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

        # Get required environment variables
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

        if not goog_cloud_dir:
            self.console.print(
                "[red]Error: GOOG_CLOUD_DIR environment variable is not set[/red]"
            )
            return
        if not goog_src_dir_base:
            self.console.print(
                "[red]Error: GOOG_SRC_DIR_BASE environment variable is not set[/red]"
            )
            return

        # Build target directory path
        target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

        try:
            # Get the CL number using branch_number command
            result = subprocess.run(
                ["branch_number"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            cl_number = result.stdout.strip()
            if not cl_number or not cl_number.isdigit():
                self.console.print(
                    f"[red]Error: branch_number returned invalid CL number: {cl_number}[/red]"
                )
                return

            # Run p4 findreviewers command
            self.console.print("[cyan]Running p4 findreviewers...[/cyan]\n")
            result = subprocess.run(
                ["p4", "findreviewers", "-c", cl_number],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            # Display the output
            if result.stdout:
                self.console.print(result.stdout)
            else:
                self.console.print("[yellow]No output from p4 findreviewers[/yellow]")

            # Wait for user to press enter before returning
            self.console.print("\n[dim]Press enter to continue...[/dim]", end="")
            input()

        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed (exit code {e.returncode})"
            if e.stderr:
                error_msg += f": {e.stderr.strip()}"
            elif e.stdout:
                error_msg += f": {e.stdout.strip()}"
            self.console.print(f"[red]{error_msg}[/red]")
        except FileNotFoundError as e:
            command_name = str(e).split("'")[1] if "'" in str(e) else "command"
            self.console.print(f"[red]{command_name} command not found[/red]")
        except Exception as e:
            self.console.print(
                f"[red]Unexpected error running findreviewers: {str(e)}[/red]"
            )

    def _handle_mail(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle 'm' (mail) action.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        if changespec.status != "Pre-Mailed":
            self.console.print(
                "[yellow]mail option only available for Pre-Mailed ChangeSpecs[/yellow]"
            )
            return changespecs, current_idx

        # Update to the changespec branch (NAME field) to ensure we're on the correct branch
        success, error_msg = update_to_changespec(
            changespec, self.console, revision=changespec.name
        )
        if not success:
            self.console.print(f"[red]Error: {error_msg}[/red]")
            return changespecs, current_idx

        # Run the mail handler
        success = handle_mail(changespec, self.console)

        if success:
            # Reload changespecs to reflect the status update
            changespecs, current_idx = self._reload_and_reposition(
                changespecs, changespec
            )

        return changespecs, current_idx

    def run(self) -> bool:
        """Run the interactive ChangeSpec navigation workflow.

        Returns:
            True if workflow completed successfully, False otherwise
        """
        # Validate filters
        is_valid, error_msg = validate_filters(
            self.status_filters, self.project_filters
        )
        if not is_valid:
            self.console.print(f"[red]Error: {error_msg}[/red]")
            return False

        # Find all ChangeSpecs
        changespecs = find_all_changespecs()

        # Apply filters
        changespecs = filter_changespecs(
            changespecs, self.status_filters, self.project_filters
        )

        if not changespecs:
            self.console.print(
                "[yellow]No ChangeSpecs found in ~/.gai/projects/*.md files[/yellow]"
            )
            return True

        self.console.print(
            f"[bold green]Found {len(changespecs)} ChangeSpec(s)[/bold green]\n"
        )

        # Interactive navigation
        current_idx = 0
        # Track navigation direction: "n" for next/forward, "p" for prev/backward
        direction = "n"

        while True:
            # Display current ChangeSpec
            changespec = changespecs[current_idx]
            self.console.clear()
            self.console.print(
                f"[bold]ChangeSpec {current_idx + 1} of {len(changespecs)}[/bold]\n"
            )
            display_changespec(changespec, self.console)

            # Determine default option based on position and direction
            default_option = self._compute_default_option(
                current_idx, len(changespecs), direction
            )

            # Show navigation prompt
            self.console.print()
            options = self._build_navigation_options(
                current_idx, len(changespecs), changespec, default_option
            )

            prompt_text = " | ".join(options) + ": "
            self.console.print(prompt_text, end="")

            # Get user input
            try:
                user_input = input().strip().lower()
                # Use default if user just pressed Enter
                if not user_input:
                    user_input = default_option
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[yellow]Aborted[/yellow]")
                return True

            # Process input
            if user_input == "n":
                result = self._handle_next(current_idx, len(changespecs) - 1)
                if result[0] is not None:
                    current_idx, direction = result
            elif user_input == "p":
                result = self._handle_prev(current_idx)
                if result[0] is not None:
                    current_idx, direction = result
            elif user_input == "s":
                changespecs, current_idx = self._handle_status_change(
                    changespec, changespecs, current_idx
                )
            elif user_input == "r":
                changespecs, current_idx = self._handle_run_workflow(
                    changespec, changespecs, current_idx
                )
            elif user_input == "f":
                self._handle_findreviewers(changespec)
            elif user_input == "m":
                changespecs, current_idx = self._handle_mail(
                    changespec, changespecs, current_idx
                )
            elif user_input == "d":
                self._handle_show_diff(changespec)
            elif user_input == "t":
                self._handle_create_tmux(changespec)
            elif user_input == "q":
                self.console.print("[green]Exiting work workflow[/green]")
                return True
            else:
                self.console.print(f"[red]Invalid option: {user_input}[/red]")

    def _compute_default_option(
        self, current_idx: int, total_count: int, direction: str
    ) -> str:
        """Compute the default navigation option.

        Args:
            current_idx: Current index in changespecs list
            total_count: Total number of changespecs
            direction: Current navigation direction ("n" or "p")

        Returns:
            Default option string ("n", "p", or "q")
        """
        is_first = current_idx == 0
        is_last = current_idx == total_count - 1
        is_only_one = total_count == 1

        if is_only_one:
            # Only one ChangeSpec: default to quit
            return "q"
        elif is_last:
            # At the last ChangeSpec: default to quit
            return "q"
        elif is_first and direction == "p":
            # At first ChangeSpec after going backward: reset direction to forward
            return "n"
        elif direction == "p":
            # Going backward: default to prev
            return "p"
        else:
            # Default case: default to next
            return "n"

    def _build_navigation_options(
        self,
        current_idx: int,
        total_count: int,
        changespec: ChangeSpec,
        default_option: str,
    ) -> list[str]:
        """Build the list of navigation option strings for display.

        Args:
            current_idx: Current index in changespecs list
            total_count: Total number of changespecs
            changespec: Current ChangeSpec
            default_option: The default option

        Returns:
            List of formatted option strings
        """
        options = []

        if current_idx > 0:
            opt_text = "[cyan]p[/cyan] (prev)"
            if default_option == "p":
                opt_text = "[black on green] → p (prev) [/black on green]"
            options.append(opt_text)

        if current_idx < total_count - 1:
            opt_text = "[cyan]n[/cyan] (next)"
            if default_option == "n":
                opt_text = "[black on green] → n (next) [/black on green]"
            options.append(opt_text)

        # Only show status change option if not blocked
        if changespec.status not in ["Blocked (EZ)", "Blocked (TDD)"]:
            options.append("[cyan]s[/cyan] (status)")

        # Only show run option for eligible ChangeSpecs
        if should_show_run_option(changespec):
            if changespec.status == "Unstarted (TDD)":
                workflow_name = "new-failing-tests"
            elif changespec.status == "TDD CL Created":
                workflow_name = "new-tdd-feature"
            elif changespec.status == "Ready for QA":
                workflow_name = "qa"
            elif changespec.status == "Failing Tests":
                workflow_name = "fix-tests"
            else:
                workflow_name = "new-ez-feature"
            options.append(f"[cyan]r[/cyan] (run {workflow_name})")

        # Only show findreviewers option if status is Pre-Mailed
        if changespec.status == "Pre-Mailed":
            options.append("[cyan]f[/cyan] (findreviewers)")

        # Only show mail option if status is Pre-Mailed
        if changespec.status == "Pre-Mailed":
            options.append("[cyan]m[/cyan] (mail)")

        # Only show diff option if CL is set
        if changespec.cl is not None and changespec.cl != "None":
            options.append("[cyan]d[/cyan] (diff)")

        # Only show tmux option if in tmux session and CL is set
        if self._is_in_tmux() and changespec.cl is not None and changespec.cl != "None":
            options.append("[cyan]t[/cyan] (tmux)")

        opt_text = "[cyan]q[/cyan] (quit)"
        if default_option == "q":
            opt_text = "[black on green] → q (quit) [/black on green]"
        options.append(opt_text)

        return options

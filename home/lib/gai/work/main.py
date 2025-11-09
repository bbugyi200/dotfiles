"""Main workflow for the work subcommand."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from new_ez_feature_workflow.main import NewEzFeatureWorkflow
from status_state_machine import VALID_STATUSES, transition_changespec_status
from workflow_base import BaseWorkflow

from .changespec import ChangeSpec, display_changespec, find_all_changespecs


class WorkWorkflow(BaseWorkflow):
    """Interactive workflow for navigating through ChangeSpecs."""

    def __init__(
        self,
        status_filters: list[str] | None = None,
        project_filters: list[str] | None = None,
    ) -> None:
        """Initialize the work workflow.

        Args:
            status_filters: List of status values to filter by (OR logic)
            project_filters: List of project basenames to filter by (OR logic)
        """
        self.console = Console()
        self.status_filters = status_filters
        self.project_filters = project_filters

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

    def _get_available_statuses(self, current_status: str) -> list[str]:
        """Get list of available statuses for selection.

        Excludes:
        - Current status
        - "Blocked" status

        Args:
            current_status: The current status value

        Returns:
            List of available status strings
        """
        return [
            status
            for status in VALID_STATUSES
            if status != current_status and status != "Blocked"
        ]

    def _prompt_status_change(self, current_status: str) -> str | None:
        """Prompt user to select a new status.

        Args:
            current_status: Current status value

        Returns:
            Selected status string, or None if cancelled
        """
        available_statuses = self._get_available_statuses(current_status)

        if not available_statuses:
            self.console.print("[yellow]No available status changes[/yellow]")
            input("Press Enter to continue...")
            return None

        self.console.print("\n[bold cyan]Select new status:[/bold cyan]")
        for idx, status in enumerate(available_statuses, 1):
            self.console.print(f"  {idx}. {status}")
        self.console.print("  0. Cancel")

        self.console.print("\nEnter choice: ", end="")

        try:
            choice = input().strip()

            if choice == "0":
                return None

            choice_idx = int(choice)
            if 1 <= choice_idx <= len(available_statuses):
                return available_statuses[choice_idx - 1]
            else:
                self.console.print("[red]Invalid choice[/red]")
                input("Press Enter to continue...")
                return None
        except (ValueError, EOFError, KeyboardInterrupt):
            self.console.print("\n[yellow]Cancelled[/yellow]")
            input("Press Enter to continue...")
            return None

    def _validate_filters(self) -> tuple[bool, str | None]:
        """Validate status and project filters.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate status filters
        if self.status_filters:
            for status in self.status_filters:
                if status not in VALID_STATUSES:
                    valid_statuses_str = ", ".join(f'"{s}"' for s in VALID_STATUSES)
                    return (
                        False,
                        f'Invalid status "{status}". Valid statuses: {valid_statuses_str}',
                    )

        # Validate project filters
        if self.project_filters:
            projects_dir = os.path.expanduser("~/.gai/projects")
            for project in self.project_filters:
                project_file = os.path.join(projects_dir, f"{project}.md")
                if not os.path.exists(project_file):
                    return (
                        False,
                        f"Project file not found: {project_file}",
                    )

        return (True, None)

    def _filter_changespecs(self, changespecs: list) -> list:
        """Filter changespecs based on status and project filters.

        Args:
            changespecs: List of ChangeSpec objects to filter

        Returns:
            Filtered list of ChangeSpec objects
        """
        from pathlib import Path

        filtered = changespecs

        # Apply status filter (OR logic)
        if self.status_filters:
            filtered = [cs for cs in filtered if cs.status in self.status_filters]

        # Apply project filter (OR logic)
        if self.project_filters:
            # Convert project filters to set of full file paths for comparison
            projects_dir = Path.home() / ".gai" / "projects"
            project_paths = {
                str(projects_dir / f"{proj}.md") for proj in self.project_filters
            }
            filtered = [cs for cs in filtered if cs.file_path in project_paths]

        return filtered

    def _should_show_run_option(self, changespec: ChangeSpec) -> bool:
        """Check if the 'r' (run) option should be shown for this ChangeSpec.

        The run option is only shown for ChangeSpecs that:
        - Have STATUS = "Not Started"
        - Have TEST TARGETS = "None" (or None)

        Args:
            changespec: The ChangeSpec object to check

        Returns:
            True if run option should be shown, False otherwise
        """
        return changespec.status == "Not Started" and (
            changespec.test_targets is None or changespec.test_targets == ["None"]
        )

    def _extract_changespec_text(
        self, project_file: str, changespec_name: str
    ) -> str | None:
        """Extract the full ChangeSpec text from a project file.

        Args:
            project_file: Path to the project file
            changespec_name: NAME of the ChangeSpec to extract

        Returns:
            The full ChangeSpec text, or None if not found
        """
        try:
            with open(project_file) as f:
                lines = f.readlines()

            in_target_changespec = False
            changespec_lines = []
            current_name = None
            consecutive_blank_lines = 0

            for i, line in enumerate(lines):
                # Check if this is a NAME field
                if line.startswith("NAME:"):
                    # If we were already in the target changespec, we're done
                    if in_target_changespec:
                        break

                    current_name = line.split(":", 1)[1].strip()
                    if current_name == changespec_name:
                        in_target_changespec = True
                        changespec_lines.append(line)
                        consecutive_blank_lines = 0
                    continue

                # If we're in the target changespec, collect lines
                if in_target_changespec:
                    # Check for end conditions
                    if line.strip().startswith("##") and i > 0:
                        break
                    if line.strip() == "":
                        consecutive_blank_lines += 1
                        if consecutive_blank_lines >= 2:
                            break
                    else:
                        consecutive_blank_lines = 0

                    changespec_lines.append(line)

            if changespec_lines:
                return "".join(changespec_lines).strip()
            return None
        except Exception as e:
            self.console.print(f"[red]Error extracting ChangeSpec text: {e}[/red]")
            return None

    def _update_to_changespec(
        self, changespec_name: str, project_file_path: str
    ) -> tuple[bool, str | None]:
        """Update working directory to the specified ChangeSpec.

        This function:
        1. Changes to $GOOG_CLOUD_DIR/<project>/$GOOG_SRC_DIR_BASE
        2. Runs bb_hg_update <name>

        Args:
            changespec_name: The NAME value from the ChangeSpec
            project_file_path: Path to the project file containing the ChangeSpec

        Returns:
            Tuple of (success, error_message)
        """
        # Extract project basename from file path
        # e.g., /path/to/foobar.md -> foobar
        project_basename = os.path.splitext(os.path.basename(project_file_path))[0]

        # Get required environment variables
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

        if not goog_cloud_dir:
            return (False, "GOOG_CLOUD_DIR environment variable is not set")
        if not goog_src_dir_base:
            return (False, "GOOG_SRC_DIR_BASE environment variable is not set")

        # Build target directory path
        target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

        # Verify directory exists
        if not os.path.exists(target_dir):
            return (False, f"Target directory does not exist: {target_dir}")
        if not os.path.isdir(target_dir):
            return (False, f"Target path is not a directory: {target_dir}")

        # Run bb_hg_update command
        try:
            subprocess.run(
                ["bb_hg_update", changespec_name],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return (True, None)
        except subprocess.CalledProcessError as e:
            error_msg = f"bb_hg_update failed (exit code {e.returncode})"
            if e.stderr:
                error_msg += f": {e.stderr.strip()}"
            elif e.stdout:
                error_msg += f": {e.stdout.strip()}"
            return (False, error_msg)
        except FileNotFoundError:
            return (False, "bb_hg_update command not found")
        except Exception as e:
            return (False, f"Unexpected error running bb_hg_update: {str(e)}")

    def run(self) -> bool:
        """Run the interactive ChangeSpec navigation workflow.

        Returns:
            True if workflow completed successfully, False otherwise
        """
        # Validate filters
        is_valid, error_msg = self._validate_filters()
        if not is_valid:
            self.console.print(f"[red]Error: {error_msg}[/red]")
            return False

        # Find all ChangeSpecs
        changespecs = find_all_changespecs()

        # Apply filters
        changespecs = self._filter_changespecs(changespecs)

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
            default_option = None
            is_first = current_idx == 0
            is_last = current_idx == len(changespecs) - 1
            is_only_one = len(changespecs) == 1

            if is_only_one:
                # Only one ChangeSpec: default to quit
                default_option = "q"
            elif is_last:
                # At the last ChangeSpec: default to quit
                default_option = "q"
            elif is_first and direction == "p":
                # At first ChangeSpec after going backward: reset direction to forward
                direction = "n"
                default_option = "n"
            elif direction == "p":
                # Going backward: default to prev
                default_option = "p"
            else:
                # Default case: default to next
                default_option = "n"

            # Show navigation prompt
            self.console.print()
            options = []
            if current_idx > 0:
                opt_text = "[cyan]p[/cyan] (prev)"
                if default_option == "p":
                    opt_text = "[black on green] → p (prev) [/black on green]"
                options.append(opt_text)
            if current_idx < len(changespecs) - 1:
                opt_text = "[cyan]n[/cyan] (next)"
                if default_option == "n":
                    opt_text = "[black on green] → n (next) [/black on green]"
                options.append(opt_text)
            # Only show status change option if not blocked
            if changespec.status != "Blocked":
                options.append("[cyan]s[/cyan] (status)")
            # Only show run option for eligible ChangeSpecs
            if self._should_show_run_option(changespec):
                options.append("[cyan]r[/cyan] (run new-ez-feature)")
            # Only show diff option if CL is set
            if changespec.cl is not None and changespec.cl != "None":
                options.append("[cyan]d[/cyan] (diff)")
            # Only show tmux option if in tmux session and CL is set
            if (
                self._is_in_tmux()
                and changespec.cl is not None
                and changespec.cl != "None"
            ):
                options.append("[cyan]t[/cyan] (tmux)")
            opt_text = "[cyan]q[/cyan] (quit)"
            if default_option == "q":
                opt_text = "[black on green] → q (quit) [/black on green]"
            options.append(opt_text)

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
                if current_idx < len(changespecs) - 1:
                    current_idx += 1
                    direction = "n"  # Set direction to forward
                else:
                    self.console.print("[yellow]Already at last ChangeSpec[/yellow]")
                    input("Press Enter to continue...")
            elif user_input == "p":
                if current_idx > 0:
                    current_idx -= 1
                    direction = "p"  # Set direction to backward
                else:
                    self.console.print("[yellow]Already at first ChangeSpec[/yellow]")
                    input("Press Enter to continue...")
            elif user_input == "s":
                # Handle status change
                if changespec.status == "Blocked":
                    self.console.print(
                        "[yellow]Cannot change status of blocked ChangeSpec[/yellow]"
                    )
                    input("Press Enter to continue...")
                else:
                    new_status = self._prompt_status_change(changespec.status)
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
                            # Reload changespecs to reflect the update
                            changespecs = find_all_changespecs()
                            changespecs = self._filter_changespecs(changespecs)
                            # Try to stay on the same changespec by name
                            for idx, cs in enumerate(changespecs):
                                if cs.name == changespec.name:
                                    current_idx = idx
                                    break
                        else:
                            self.console.print(f"[red]Error: {error_msg}[/red]")
                        input("Press Enter to continue...")
            elif user_input == "r":
                # Handle run new-ez-feature workflow
                if not self._should_show_run_option(changespec):
                    self.console.print(
                        "[yellow]Run option not available for this ChangeSpec[/yellow]"
                    )
                    input("Press Enter to continue...")
                else:
                    # Extract project basename and changespec text
                    project_basename = os.path.splitext(
                        os.path.basename(changespec.file_path)
                    )[0]
                    changespec_text = self._extract_changespec_text(
                        changespec.file_path, changespec.name
                    )

                    if not changespec_text:
                        self.console.print(
                            "[red]Error: Could not extract ChangeSpec text[/red]"
                        )
                        input("Press Enter to continue...")
                        continue

                    # Update to the changespec (cd and bb_hg_update)
                    success, error_msg = self._update_to_changespec(
                        changespec.name, changespec.file_path
                    )
                    if not success:
                        self.console.print(f"[red]Error: {error_msg}[/red]")
                        input("Press Enter to continue...")
                        continue

                    # Get target directory for running workflow
                    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
                    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
                    # These should be set since _update_to_changespec already validated them
                    assert goog_cloud_dir is not None
                    assert goog_src_dir_base is not None
                    target_dir = os.path.join(
                        goog_cloud_dir, project_basename, goog_src_dir_base
                    )

                    # Update STATUS to "Creating EZ CL..."
                    success, old_status, error_msg = transition_changespec_status(
                        changespec.file_path,
                        changespec.name,
                        "Creating EZ CL...",
                        validate=True,
                    )
                    if not success:
                        self.console.print(
                            f"[red]Error updating status: {error_msg}[/red]"
                        )
                        input("Press Enter to continue...")
                        continue

                    # Track whether workflow succeeded for proper rollback
                    workflow_succeeded = False

                    try:
                        # Run the new-ez-feature workflow
                        self.console.print(
                            "[cyan]Running new-ez-feature workflow...[/cyan]"
                        )
                        workflow = NewEzFeatureWorkflow(
                            project_name=project_basename,
                            design_docs_dir=target_dir,
                            changespec_text=changespec_text,
                            context_file_directory=None,
                        )
                        workflow_succeeded = workflow.run()

                        if workflow_succeeded:
                            # Run bb_hg_presubmit
                            self.console.print(
                                "[cyan]Running bb_hg_presubmit...[/cyan]"
                            )
                            try:
                                subprocess.run(
                                    ["bb_hg_presubmit"],
                                    cwd=target_dir,
                                    check=True,
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

                            # Update STATUS to "Running TAP Tests"
                            success, _, error_msg = transition_changespec_status(
                                changespec.file_path,
                                changespec.name,
                                "Running TAP Tests",
                                validate=True,
                            )
                            if success:
                                self.console.print(
                                    "[green]Workflow completed successfully![/green]"
                                )
                            else:
                                self.console.print(
                                    f"[yellow]Warning: Could not update status to 'Running TAP Tests': {error_msg}[/yellow]"
                                )
                        else:
                            self.console.print(
                                "[red]Workflow failed - reverting status[/red]"
                            )

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
                        # Revert status to "Not Started" if workflow didn't succeed
                        if not workflow_succeeded:
                            success, _, error_msg = transition_changespec_status(
                                changespec.file_path,
                                changespec.name,
                                "Not Started",
                                validate=True,
                            )
                            if not success:
                                self.console.print(
                                    f"[red]Critical: Failed to revert status: {error_msg}[/red]"
                                )

                        # Reload changespecs to reflect updates
                        changespecs = find_all_changespecs()
                        changespecs = self._filter_changespecs(changespecs)
                        # Try to stay on the same changespec by name
                        for idx, cs in enumerate(changespecs):
                            if cs.name == changespec.name:
                                current_idx = idx
                                break

                    input("Press Enter to continue...")
            elif user_input == "d":
                # Handle diff
                if changespec.cl is None or changespec.cl == "None":
                    self.console.print(
                        "[yellow]Cannot show diff: CL is not set[/yellow]"
                    )
                else:
                    # Update to the changespec
                    success, error_msg = self._update_to_changespec(
                        changespec.name, changespec.file_path
                    )
                    if not success:
                        self.console.print(f"[red]Error: {error_msg}[/red]")
                    else:
                        # Run branch_diff
                        # Get target directory for running branch_diff
                        project_basename = os.path.splitext(
                            os.path.basename(changespec.file_path)
                        )[0]
                        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
                        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
                        # These should be set since _update_to_changespec already validated them
                        assert goog_cloud_dir is not None
                        assert goog_src_dir_base is not None
                        target_dir = os.path.join(
                            goog_cloud_dir, project_basename, goog_src_dir_base
                        )

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
                            self.console.print(
                                "[red]branch_diff command not found[/red]"
                            )
                        except Exception as e:
                            self.console.print(
                                f"[red]Unexpected error running branch_diff: {str(e)}[/red]"
                            )
            elif user_input == "t":
                # Handle tmux window creation
                if changespec.cl is None or changespec.cl == "None":
                    self.console.print(
                        "[yellow]Cannot create tmux window: CL is not set[/yellow]"
                    )
                elif not self._is_in_tmux():
                    self.console.print(
                        "[yellow]Cannot create tmux window: not in tmux session[/yellow]"
                    )
                else:
                    # Extract project basename
                    project_basename = os.path.splitext(
                        os.path.basename(changespec.file_path)
                    )[0]

                    # Get required environment variables
                    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
                    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

                    if not goog_cloud_dir:
                        self.console.print(
                            "[red]Error: GOOG_CLOUD_DIR environment variable is not set[/red]"
                        )
                    elif not goog_src_dir_base:
                        self.console.print(
                            "[red]Error: GOOG_SRC_DIR_BASE environment variable is not set[/red]"
                        )
                    else:
                        # Build target directory path
                        target_dir = os.path.join(
                            goog_cloud_dir, project_basename, goog_src_dir_base
                        )

                        # Build the command to run in the new tmux window
                        # cd to the directory, run bb_hg_update, then start a shell
                        tmux_cmd = (
                            f"cd {target_dir} && "
                            f"bb_hg_update {changespec.name} && "
                            f"exec $SHELL"
                        )

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
            elif user_input == "q":
                self.console.print("[green]Exiting work workflow[/green]")
                return True
            else:
                self.console.print(f"[red]Invalid option: {user_input}[/red]")
                input("Press Enter to continue...")

"""Main workflow for the work subcommand."""

import os
import sys
import termios
import tty
from typing import Literal

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import reset_changespec_cl, transition_changespec_status
from workflow_base import BaseWorkflow

from .changespec import ChangeSpec, display_changespec, find_all_changespecs
from .filters import filter_changespecs, validate_filters
from .handlers import (
    handle_findreviewers,
    handle_mail,
    handle_run_crs_workflow,
    handle_run_fix_tests_workflow,
    handle_run_qa_workflow,
    handle_run_query,
    handle_run_tdd_feature_workflow,
    handle_run_workflow,
    handle_show_diff,
    handle_tricorder,
)
from .operations import unblock_child_changespecs
from .status import prompt_status_change


def _wait_for_user_input() -> None:
    """Wait for the user to press any key to continue."""
    print("\nPress any key to continue...", end="", flush=True)

    # Save current terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Set terminal to raw mode to read a single character
        tty.setraw(fd)
        sys.stdin.read(1)
    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Print newline after the key press
        print()


class WorkWorkflow(BaseWorkflow):
    """Interactive workflow for navigating through ChangeSpecs."""

    def __init__(
        self,
        status_filters: list[str] | None = None,
        project_filters: list[str] | None = None,
        model_size_override: Literal["little", "big"] | None = None,
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
        if changespec.status in ["Blocked", "Blocked"]:
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

                # If status changed to Unstarted, reset the CL field
                if new_status == "Unstarted":
                    if reset_changespec_cl(changespec.file_path, changespec.name):
                        self.console.print("[green]CL field reset to None[/green]")

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
        self,
        changespec: ChangeSpec,
        changespecs: list[ChangeSpec],
        current_idx: int,
        workflow_index: int = 0,
    ) -> tuple[list[ChangeSpec], int]:
        """Handle 'r' (run workflow) action.

        Runs workflow based on available workflows for the ChangeSpec.
        When multiple workflows are available, workflow_index selects which one to run.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index
            workflow_index: Index of workflow to run (default 0)

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        return handle_run_workflow(
            self, changespec, changespecs, current_idx, workflow_index
        )

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
        return handle_run_tdd_feature_workflow(
            self, changespec, changespecs, current_idx
        )

    def _handle_run_qa_workflow(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle running qa workflow for 'Pre-Mailed' or 'Mailed' status.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        return handle_run_qa_workflow(self, changespec, changespecs, current_idx)

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
        return handle_run_fix_tests_workflow(self, changespec, changespecs, current_idx)

    def _handle_run_crs_workflow(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle running crs workflow for 'Mailed' status.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        return handle_run_crs_workflow(self, changespec, changespecs, current_idx)

    def _handle_show_diff(self, changespec: ChangeSpec) -> None:
        """Handle 'd' (show diff) action.

        Args:
            changespec: Current ChangeSpec
        """
        return handle_show_diff(self, changespec)

    def _handle_tricorder(self, changespec: ChangeSpec) -> None:
        """Handle 't' (tricorder) action.

        Args:
            changespec: Current ChangeSpec
        """
        return handle_tricorder(self, changespec)

    def _handle_findreviewers(self, changespec: ChangeSpec) -> None:
        """Handle 'f' (findreviewers) action.

        Args:
            changespec: Current ChangeSpec
        """
        return handle_findreviewers(self, changespec)

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
        return handle_mail(self, changespec, changespecs, current_idx)

    def _handle_run_query(self, changespec: ChangeSpec) -> None:
        """Handle 'R' (run query) action.

        Args:
            changespec: Current ChangeSpec
        """
        return handle_run_query(self, changespec)

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
                "[yellow]No ChangeSpecs found in ~/.gai/projects/<project>/<project>.gp files[/yellow]"
            )
            return True

        self.console.print(
            f"[bold green]Found {len(changespecs)} ChangeSpec(s)[/bold green]\n"
        )

        # Interactive navigation
        current_idx = 0
        # Track navigation direction: "n" for next/forward, "p" for prev/backward
        direction = "n"
        # Track whether to wait before clearing screen (for actions that produce output)
        should_wait_before_clear = False

        while True:
            # Wait for user to press a key before clearing screen (only after actions with output)
            if should_wait_before_clear:
                _wait_for_user_input()
            should_wait_before_clear = (
                False  # Reset flag, will be set by actions that need it
            )

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
                # No wait needed for navigation
            elif user_input == "p":
                result = self._handle_prev(current_idx)
                if result[0] is not None:
                    current_idx, direction = result
                # No wait needed for navigation
            elif user_input == "s":
                changespecs, current_idx = self._handle_status_change(
                    changespec, changespecs, current_idx
                )
                # No wait needed - status changes are displayed inline
            elif user_input == "r" or user_input.startswith("r"):
                # Handle both "r" and "r1", "r2", etc.
                workflow_index = 0
                if len(user_input) > 1 and user_input[1:].isdigit():
                    workflow_index = int(user_input[1:]) - 1
                changespecs, current_idx = self._handle_run_workflow(
                    changespec, changespecs, current_idx, workflow_index
                )
                should_wait_before_clear = True  # Workflows produce lots of output
            elif user_input == "f":
                self._handle_findreviewers(changespec)
                # No wait needed - findreviewers handles user input
            elif user_input == "m":
                changespecs, current_idx = self._handle_mail(
                    changespec, changespecs, current_idx
                )
                should_wait_before_clear = True  # Mail shows output
            elif user_input == "d":
                self._handle_show_diff(changespec)
                # No wait needed - branch_diff uses a pager that handles user input
            elif user_input == "t":
                self._handle_tricorder(changespec)
                # No wait needed - tricorder handler prompts for key press
            elif user_input == "R":
                self._handle_run_query(changespec)
                should_wait_before_clear = True  # Query output needs to be read
            elif user_input == "q":
                self.console.print("[green]Exiting work workflow[/green]")
                return True
            else:
                self.console.print(f"[red]Invalid option: {user_input}[/red]")
                should_wait_before_clear = True  # Error message needs to be read

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
        if changespec.status not in ["Blocked", "Blocked"]:
            options.append("[cyan]s[/cyan] (status)")

        # Show run options for eligible ChangeSpecs
        # Use numbered keys (r1, r2, etc.) if there are multiple workflows
        from .operations import get_available_workflows

        workflows = get_available_workflows(changespec)
        if len(workflows) == 1:
            options.append(f"[cyan]r[/cyan] (run {workflows[0]})")
        elif len(workflows) > 1:
            for i, workflow_name in enumerate(workflows, start=1):
                options.append(f"[cyan]r{i}[/cyan] (run {workflow_name})")

        # Only show findreviewers option if status is Pre-Mailed
        if changespec.status == "Pre-Mailed":
            options.append("[cyan]f[/cyan] (findreviewers)")

        # Only show mail option if status is Pre-Mailed
        if changespec.status == "Pre-Mailed":
            options.append("[cyan]m[/cyan] (mail)")

        # Only show diff option if CL is set
        if changespec.cl is not None and changespec.cl != "None":
            options.append("[cyan]d[/cyan] (diff)")

        # Only show tricorder option if status is Pre-Mailed
        if changespec.status == "Pre-Mailed":
            options.append("[cyan]t[/cyan] (tricorder)")

        # Always show run query option
        options.append("[cyan]R[/cyan] (run query)")

        opt_text = "[cyan]q[/cyan] (quit)"
        if default_option == "q":
            opt_text = "[black on green] → q (quit) [/black on green]"
        options.append(opt_text)

        return options

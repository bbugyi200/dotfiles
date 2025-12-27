"""Main workflow for the work subcommand."""

import os
import sys
from typing import Literal

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from workflow_base import BaseWorkflow

from ..changespec import ChangeSpec, find_all_changespecs
from ..display import display_changespec
from ..filters import filter_changespecs, validate_filters
from ..handlers import (
    handle_edit_hooks,
    handle_findreviewers,
    handle_mail,
    handle_run_query,
    handle_run_workflow,
    handle_show_diff,
)
from .actions import (
    handle_accept_proposal,
    handle_next,
    handle_prev,
    handle_refresh,
    handle_status_change,
    handle_view,
)
from .input_utils import input_with_timeout, wait_for_user_input
from .navigation import build_navigation_options, compute_default_option


class WorkWorkflow(BaseWorkflow):
    """Interactive workflow for navigating through ChangeSpecs."""

    def __init__(
        self,
        status_filters: list[str] | None = None,
        project_filters: list[str] | None = None,
        model_size_override: Literal["little", "big"] | None = None,
        refresh_interval: int = 60,
    ) -> None:
        """Initialize the work workflow.

        Args:
            status_filters: List of status values to filter by (OR logic)
            project_filters: List of project basenames to filter by (OR logic)
            model_size_override: Override model size for all GeminiCommandWrapper instances
            refresh_interval: Auto-refresh interval in seconds (0 to disable, default: 60)
        """
        self.console = Console()
        self.status_filters = status_filters
        self.project_filters = project_filters
        self.refresh_interval = refresh_interval

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
            self.console.print("[yellow]No ChangeSpecs found matching filters[/yellow]")
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
        # Track partial input that was preserved across auto-refresh
        pending_input = ""

        while True:
            # Wait for user to press a key before clearing screen (only after actions with output)
            if should_wait_before_clear:
                wait_for_user_input()
                pending_input = ""  # Clear pending input after explicit wait
            should_wait_before_clear = (
                False  # Reset flag, will be set by actions that need it
            )

            # Check if changespecs list is empty (can happen after reload if filters exclude all)
            if not changespecs:
                self.console.print(
                    "[yellow]No ChangeSpecs match the current filters. Exiting.[/yellow]"
                )
                return True

            # Ensure current_idx is within bounds (can be out of range after reload)
            if current_idx >= len(changespecs):
                current_idx = len(changespecs) - 1

            # Display current ChangeSpec
            changespec = changespecs[current_idx]
            self.console.clear()
            refresh_info = (
                f" [dim](refresh: {self.refresh_interval}s)[/dim]"
                if self.refresh_interval > 0
                else ""
            )
            self.console.print(
                f"[bold]ChangeSpec {current_idx + 1} of {len(changespecs)}[/bold]{refresh_info}\n"
            )
            display_changespec(changespec, self.console)  # Ignore return value

            # Determine default option based on position and direction
            default_option = compute_default_option(
                current_idx, len(changespecs), direction
            )

            # Show navigation prompt
            self.console.print()
            options = build_navigation_options(
                current_idx, len(changespecs), changespec, default_option
            )

            prompt_text = " | ".join(options) + ": "
            self.console.print(prompt_text, end="")

            # Get user input with optional timeout for auto-refresh
            # Note: Don't lowercase - we need to distinguish 'r' (run workflow) from 'R' (run query)
            try:
                user_input, pending_input = input_with_timeout(
                    self.refresh_interval, pending_input
                )
                # Timeout occurred - auto-refresh (preserve pending_input for next iteration)
                if user_input is None:
                    user_input = "y"
                # Use default if user just pressed Enter
                elif not user_input:
                    user_input = default_option
                    pending_input = ""  # Clear pending input on successful input
                else:
                    pending_input = ""  # Clear pending input on successful input
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[yellow]Aborted[/yellow]")
                return True

            # Process input
            should_wait_before_clear = self._process_input(
                user_input,
                changespec,
                changespecs,
                current_idx,
                direction,
            )

            # Update state based on processed input
            result = self._get_updated_state(
                user_input, changespec, changespecs, current_idx, direction
            )
            if result is None:
                # Quit was selected
                return True
            changespecs, current_idx, direction = result

    def _process_input(
        self,
        user_input: str,
        changespec: ChangeSpec,
        changespecs: list[ChangeSpec],
        current_idx: int,
        direction: str,
    ) -> bool:
        """Process user input and return whether to wait before clearing screen.

        Args:
            user_input: The user's input string
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index
            direction: Current navigation direction

        Returns:
            True if should wait before clearing screen, False otherwise
        """
        # Actions that produce output and need waiting
        if user_input == "r" or user_input.startswith("r"):
            return True
        elif user_input == "m":
            return True
        elif user_input == "R":
            return True
        elif user_input == "v":
            return True
        elif user_input.startswith("a"):
            return True
        elif user_input not in ("n", "p", "s", "f", "d", "h", "y", "q"):
            # Unknown input - show error
            self.console.print(f"[red]Invalid option: {user_input}[/red]")
            return True
        return False

    def _get_updated_state(
        self,
        user_input: str,
        changespec: ChangeSpec,
        changespecs: list[ChangeSpec],
        current_idx: int,
        direction: str,
    ) -> tuple[list[ChangeSpec], int, str] | None:
        """Get updated state after processing user input.

        Args:
            user_input: The user's input string
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index
            direction: Current navigation direction

        Returns:
            Tuple of (updated_changespecs, updated_index, updated_direction)
            or None if quit was selected
        """
        if user_input == "n":
            result = handle_next(self, current_idx, len(changespecs) - 1)
            if result[0] is not None:
                return changespecs, result[0], result[1]
        elif user_input == "p":
            result = handle_prev(self, current_idx)
            if result[0] is not None:
                return changespecs, result[0], result[1]
        elif user_input == "s":
            changespecs, current_idx = handle_status_change(
                self, changespec, changespecs, current_idx
            )
        elif user_input == "r" or user_input.startswith("r"):
            # Handle both "r" and "r1", "r2", etc.
            workflow_index = 0
            if len(user_input) > 1 and user_input[1:].isdigit():
                workflow_index = int(user_input[1:]) - 1
            changespecs, current_idx = handle_run_workflow(
                self, changespec, changespecs, current_idx, workflow_index
            )
        elif user_input == "f":
            handle_findreviewers(self, changespec)
        elif user_input == "m":
            changespecs, current_idx = handle_mail(
                self, changespec, changespecs, current_idx
            )
        elif user_input == "d":
            handle_show_diff(self, changespec)
        elif user_input == "h":
            changespecs, current_idx = handle_edit_hooks(
                self, changespec, changespecs, current_idx
            )
        elif user_input == "R":
            handle_run_query(self, changespec)
        elif user_input == "v":
            handle_view(self, changespec)
        elif user_input == "y":
            changespecs, current_idx = handle_refresh(
                self, changespec, changespecs, current_idx
            )
        elif user_input == "q":
            self.console.print("[green]Exiting work workflow[/green]")
            return None
        elif user_input.startswith("a"):
            changespecs, current_idx = handle_accept_proposal(
                self, changespec, changespecs, current_idx, user_input
            )

        return changespecs, current_idx, direction

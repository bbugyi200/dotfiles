"""Main workflow for the search subcommand."""

import os
import sys
from typing import Literal

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from workflow_base import BaseWorkflow

from ..changespec import ChangeSpec, find_all_changespecs
from ..display import display_changespec, display_search_query
from ..handlers import (
    handle_edit_hooks,
    handle_findreviewers,
    handle_mail,
    handle_run_query,
    handle_run_workflow,
    handle_show_diff,
)
from ..query import QueryParseError, evaluate_query, parse_query
from ..query.types import QueryExpr
from .actions import (
    handle_accept_proposal,
    handle_next,
    handle_prev,
    handle_refresh,
    handle_status_change,
    handle_view,
)
from .input_utils import (
    countdown_with_quit,
    input_with_readline,
    input_with_timeout,
    wait_for_user_input,
)
from .navigation import build_navigation_options, compute_default_option


class SearchWorkflow(BaseWorkflow):
    """Interactive workflow for navigating through ChangeSpecs."""

    def __init__(
        self,
        query: str,
        model_size_override: Literal["little", "big"] | None = None,
        refresh_interval: int = 60,
    ) -> None:
        """Initialize the search workflow.

        Args:
            query: Query string for filtering ChangeSpecs (uses query language)
            model_size_override: Override model size for all GeminiCommandWrapper instances
            refresh_interval: Auto-refresh interval in seconds (0 to disable, default: 60)

        Raises:
            QueryParseError: If the query string is invalid
        """
        self.console = Console()
        self.query_string = query
        self.parsed_query: QueryExpr = parse_query(
            query
        )  # Parse early for error detection
        self.refresh_interval = refresh_interval

        # Set global model size override in environment if specified
        if model_size_override:
            os.environ["GAI_MODEL_SIZE_OVERRIDE"] = model_size_override

    @property
    def name(self) -> str:
        """Return the name of this workflow."""
        return "search"

    @property
    def description(self) -> str:
        """Return a description of what this workflow does."""
        return "Interactively navigate through ChangeSpecs matching a query"

    def _filter_changespecs(self, changespecs: list[ChangeSpec]) -> list[ChangeSpec]:
        """Filter changespecs using the parsed query.

        Args:
            changespecs: List of changespecs to filter

        Returns:
            Filtered list of changespecs matching the query
        """
        return [cs for cs in changespecs if evaluate_query(self.parsed_query, cs)]

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
        new_changespecs = self._filter_changespecs(new_changespecs)

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
        # Find all ChangeSpecs and apply query filter
        changespecs = find_all_changespecs()
        changespecs = self._filter_changespecs(changespecs)

        self.console.print(
            f"[bold green]Found {len(changespecs)} ChangeSpec(s) matching query[/bold green]\n"
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

            # Clear screen first
            self.console.clear()

            refresh_info = (
                f" [dim](refresh: {self.refresh_interval}s)[/dim]"
                if self.refresh_interval > 0
                else ""
            )

            # Check if changespecs list is empty (can happen after reload if query matches nothing)
            if not changespecs:
                self.console.print("[bold]ChangeSpec 0 of 0[/bold]\n")
                self.console.print(
                    f"[yellow]No ChangeSpecs match query: {self.query_string}[/yellow]\n"
                )
                self.console.print()

                # Special countdown for empty results (10 seconds)
                quit_requested = countdown_with_quit(self.console, seconds=10)
                if quit_requested:
                    self.console.print("[green]Exiting search workflow[/green]")
                    return True

                # Auto-refresh after countdown
                changespecs = find_all_changespecs()
                changespecs = self._filter_changespecs(changespecs)
                current_idx = 0
                continue

            # Ensure current_idx is within bounds (can be out of range after reload)
            if current_idx >= len(changespecs):
                current_idx = len(changespecs) - 1

            # Display current ChangeSpec
            changespec = changespecs[current_idx]
            self.console.print(
                f"[bold]ChangeSpec {current_idx + 1} of {len(changespecs)}[/bold]{refresh_info}\n"
            )
            display_search_query(self.query_string, self.console)
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
        elif user_input not in ("n", "p", "s", "f", "d", "h", "y", "q", "/"):
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
            self.console.print("[green]Exiting search workflow[/green]")
            return None
        elif user_input.startswith("a"):
            changespecs, current_idx = handle_accept_proposal(
                self, changespec, changespecs, current_idx, user_input
            )
        elif user_input == "/":
            edit_result = self._handle_edit_query(changespecs)
            if edit_result is not None:
                return edit_result[0], edit_result[1], direction

        return changespecs, current_idx, direction

    def _handle_edit_query(
        self, changespecs: list[ChangeSpec]
    ) -> tuple[list[ChangeSpec], int] | None:
        """Handle the edit query command.

        Args:
            changespecs: Current list of changespecs (unused, will be reloaded)

        Returns:
            Tuple of (new_changespecs, new_index) if query was changed,
            None if cancelled or unchanged.
        """
        del changespecs  # Unused - will reload from files

        new_query = input_with_readline("Edit query: ", self.query_string)

        if new_query is None or new_query == self.query_string:
            # Cancelled or unchanged
            return None

        # Try to parse the new query
        try:
            new_parsed = parse_query(new_query)
        except QueryParseError as e:
            self.console.print(f"[red]Invalid query: {e}[/red]")
            return None

        # Update query state
        self.query_string = new_query
        self.parsed_query = new_parsed

        # Re-filter changespecs
        all_changespecs = find_all_changespecs()
        filtered = self._filter_changespecs(all_changespecs)

        return filtered, 0  # Reset to first result

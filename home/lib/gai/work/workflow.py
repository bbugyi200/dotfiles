"""Main workflow for the work subcommand."""

import os
import sys
import termios
import tty
from typing import Literal

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import transition_changespec_status
from workflow_base import BaseWorkflow

from .changespec import ChangeSpec, display_changespec, find_all_changespecs
from .cl_status import sync_all_changespecs
from .field_updates import (
    add_failing_test_targets,
    remove_failed_markers_from_test_targets,
)
from .filters import filter_changespecs, validate_filters
from .handlers import (
    handle_findreviewers,
    handle_mail,
    handle_run_crs_workflow,
    handle_run_fix_tests_workflow,
    handle_run_qa_workflow,
    handle_run_query,
    handle_run_workflow,
    handle_show_diff,
    handle_tricorder,
)
from .revert import revert_changespec
from .status import (
    STATUS_FAILING_TESTS,
    STATUS_REVERTED,
    prompt_failing_test_targets,
    prompt_status_change,
)


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
        new_status = prompt_status_change(self.console, changespec.status)
        if new_status:
            # Special handling for "Reverted" status - run revert workflow
            if new_status == STATUS_REVERTED:
                success, error_msg = revert_changespec(changespec, self.console)
                if not success:
                    self.console.print(f"[red]Error reverting: {error_msg}[/red]")
                    return changespecs, current_idx

                # Reload changespecs to reflect the update
                changespecs, current_idx = self._reload_and_reposition(
                    changespecs, changespec
                )
                return changespecs, current_idx

            # Special handling for "Failing Tests" status - prompt for test targets
            if new_status == STATUS_FAILING_TESTS:
                failing_targets = prompt_failing_test_targets(self.console)
                if failing_targets is None:
                    # User cancelled
                    return changespecs, current_idx

                # Add failing test targets to the ChangeSpec
                success, error_msg = add_failing_test_targets(
                    changespec.file_path, changespec.name, failing_targets
                )
                if not success:
                    self.console.print(
                        f"[red]Error adding test targets: {error_msg}[/red]"
                    )
                    return changespecs, current_idx

                self.console.print(
                    f"[green]Added {len(failing_targets)} failing test target(s)[/green]"
                )

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

                # If transitioning FROM "Failing Tests", remove FAILED markers
                if (
                    old_status == STATUS_FAILING_TESTS
                    and new_status != STATUS_FAILING_TESTS
                ):
                    rm_success, rm_error = remove_failed_markers_from_test_targets(
                        changespec.file_path, changespec.name
                    )
                    if rm_success:
                        self.console.print(
                            "[green]Removed (FAILED) markers from test targets[/green]"
                        )
                    elif rm_error:
                        self.console.print(f"[yellow]Warning: {rm_error}[/yellow]")

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

    def _handle_run_qa_workflow(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle running qa workflow for 'Drafted' or 'Mailed' status.

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
        """Handle running fix-tests workflow.

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

    def _handle_sync(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle 'y' (sync) action - sync all eligible ChangeSpecs.

        Syncs all ChangeSpecs with "Mailed" or "Changes Requested" status
        that have no parent or a submitted parent.

        Args:
            changespec: Current ChangeSpec (used for repositioning after sync)
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        # Force sync all eligible ChangeSpecs (ignore time-based throttling)
        if sync_all_changespecs(self.console, force=True) > 0:
            # Reload changespecs to reflect any status changes
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

        # Sync all mailed/changes-requested ChangeSpecs across all projects on startup
        # This runs before filtering so it checks ALL changespecs, not just filtered ones
        sync_all_changespecs(self.console)

        # Find all ChangeSpecs (after sync, so we get updated statuses)
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

        while True:
            # Wait for user to press a key before clearing screen (only after actions with output)
            if should_wait_before_clear:
                _wait_for_user_input()
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
                    # Sync all eligible ChangeSpecs across all projects
                    new_changespec = changespecs[current_idx]
                    if sync_all_changespecs(self.console) > 0:
                        # Reload changespecs to reflect any status changes
                        changespecs, current_idx = self._reload_and_reposition(
                            changespecs, new_changespec
                        )
                # No wait needed for navigation
            elif user_input == "p":
                result = self._handle_prev(current_idx)
                if result[0] is not None:
                    current_idx, direction = result
                    # Sync all eligible ChangeSpecs across all projects
                    new_changespec = changespecs[current_idx]
                    if sync_all_changespecs(self.console) > 0:
                        # Reload changespecs to reflect any status changes
                        changespecs, current_idx = self._reload_and_reposition(
                            changespecs, new_changespec
                        )
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
            elif user_input == "y":
                changespecs, current_idx = self._handle_sync(
                    changespec, changespecs, current_idx
                )
                should_wait_before_clear = True  # Sync output needs to be read
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

        Options are sorted alphabetically (case-insensitive, lowercase before uppercase).

        Args:
            current_idx: Current index in changespecs list
            total_count: Total number of changespecs
            changespec: Current ChangeSpec
            default_option: The default option

        Returns:
            List of formatted option strings
        """
        # Collect options as (sort_key, formatted_text) tuples
        # Sort key format: (lowercase_letter, is_uppercase, number_suffix)
        # This ensures case-insensitive sort with lowercase before uppercase
        options_with_keys: list[tuple[tuple[str, bool, int], str]] = []

        def make_sort_key(key: str) -> tuple[str, bool, int]:
            """Create a sort key for alphabetical ordering.

            Returns (lowercase_letter, is_uppercase, number_suffix) tuple.
            """
            base_char = key[0]
            is_upper = base_char.isupper()
            # Extract number suffix if present (e.g., "r1" -> 1, "r2" -> 2)
            num_suffix = 0
            if len(key) > 1 and key[1:].isdigit():
                num_suffix = int(key[1:])
            return (base_char.lower(), is_upper, num_suffix)

        def format_option(key: str, label: str, is_default: bool) -> str:
            """Format an option for display."""
            if is_default:
                return f"[black on green] → {key} ({label}) [/black on green]"
            return f"[cyan]{key}[/cyan] ({label})"

        # Only show diff option if CL is set
        if changespec.cl is not None and changespec.cl != "None":
            options_with_keys.append(
                (make_sort_key("d"), format_option("d", "diff", False))
            )

        # Only show findreviewers option if status is Drafted
        if changespec.status == "Drafted":
            options_with_keys.append(
                (make_sort_key("f"), format_option("f", "findreviewers", False))
            )

        # Only show mail option if status is Drafted
        if changespec.status == "Drafted":
            options_with_keys.append(
                (make_sort_key("m"), format_option("m", "mail", False))
            )

        # Navigation: next
        if current_idx < total_count - 1:
            options_with_keys.append(
                (make_sort_key("n"), format_option("n", "next", default_option == "n"))
            )

        # Navigation: prev
        if current_idx > 0:
            options_with_keys.append(
                (make_sort_key("p"), format_option("p", "prev", default_option == "p"))
            )

        # Quit option
        options_with_keys.append(
            (make_sort_key("q"), format_option("q", "quit", default_option == "q"))
        )

        # Show run options for eligible ChangeSpecs
        # Use numbered keys (r1, r2, etc.) if there are multiple workflows
        from .operations import get_available_workflows

        workflows = get_available_workflows(changespec)
        if len(workflows) == 1:
            options_with_keys.append(
                (make_sort_key("r"), format_option("r", f"run {workflows[0]}", False))
            )
        elif len(workflows) > 1:
            for i, workflow_name in enumerate(workflows, start=1):
                key = f"r{i}"
                options_with_keys.append(
                    (
                        make_sort_key(key),
                        format_option(key, f"run {workflow_name}", False),
                    )
                )

        # Run query option (uppercase R)
        options_with_keys.append(
            (make_sort_key("R"), format_option("R", "run query", False))
        )

        # Only show status change option if not blocked
        # Status change is always available
        options_with_keys.append(
            (make_sort_key("s"), format_option("s", "status", False))
        )

        # Only show tricorder option if status is Drafted
        if changespec.status == "Drafted":
            options_with_keys.append(
                (make_sort_key("t"), format_option("t", "tricorder", False))
            )

        # Sync option is always available - syncs all eligible ChangeSpecs
        options_with_keys.append(
            (make_sort_key("y"), format_option("y", "sync all", False))
        )

        # Sort by the sort key and return just the formatted strings
        options_with_keys.sort(key=lambda x: x[0])
        return [opt[1] for opt in options_with_keys]

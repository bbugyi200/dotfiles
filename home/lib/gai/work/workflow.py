"""Main workflow for the work subcommand."""

import os
import select
import sys
import termios
import time
import tty
from typing import Literal

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import transition_changespec_status
from workflow_base import BaseWorkflow

from .changespec import ChangeSpec, display_changespec, find_all_changespecs
from .filters import filter_changespecs, validate_filters
from .handlers import (
    handle_add_hook,
    handle_findreviewers,
    handle_mail,
    handle_run_crs_workflow,
    handle_run_fix_tests_workflow,
    handle_run_qa_workflow,
    handle_run_query,
    handle_run_workflow,
    handle_show_diff,
)
from .revert import revert_changespec
from .status import (
    STATUS_REVERTED,
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


def _input_with_timeout(
    timeout_seconds: int, initial_input: str = ""
) -> tuple[str | None, str]:
    """Read a line of input with a timeout, preserving partial input.

    Uses raw terminal mode to read characters one at a time, allowing us to
    preserve any partial input if a timeout occurs.

    Args:
        timeout_seconds: Maximum seconds to wait for input (0 means no timeout)
        initial_input: Previously typed partial input to restore

    Returns:
        Tuple of (completed_input, partial_input):
        - If user completes input (presses Enter): (input_string, "")
        - If timeout occurs: (None, partial_input_so_far)

    Raises:
        EOFError: If EOF is encountered
        KeyboardInterrupt: If Ctrl+C is pressed
    """
    if timeout_seconds <= 0:
        # No timeout, use regular input (but still handle initial_input)
        if initial_input:
            # Print the initial input so user sees it
            print(initial_input, end="", flush=True)
        result = input()
        return (initial_input + result).strip(), ""

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    buffer = initial_input

    # Print initial input if any
    if initial_input:
        print(initial_input, end="", flush=True)

    try:
        # Set terminal to cbreak mode (non-canonical, no echo)
        tty.setcbreak(fd)

        deadline = time.time() + timeout_seconds

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                # Timeout - return None with partial input
                print()  # Move to next line
                return None, buffer

            # Wait for input with remaining timeout
            ready, _, _ = select.select([sys.stdin], [], [], remaining)

            if not ready:
                # Timeout - return None with partial input
                print()  # Move to next line
                return None, buffer

            # Read one character
            char = sys.stdin.read(1)

            if not char:
                raise EOFError()

            if char == "\x03":  # Ctrl+C
                raise KeyboardInterrupt()

            if char == "\x04":  # Ctrl+D (EOF)
                raise EOFError()

            if char in ("\r", "\n"):  # Enter
                print()  # Move to next line
                return buffer.strip(), ""

            if char == "\x7f" or char == "\x08":  # Backspace (DEL or BS)
                if buffer:
                    buffer = buffer[:-1]
                    # Erase character on screen: move back, space, move back
                    print("\b \b", end="", flush=True)
            else:
                # Regular character - add to buffer and echo
                buffer += char
                print(char, end="", flush=True)

    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class WorkWorkflow(BaseWorkflow):
    """Interactive workflow for navigating through ChangeSpecs."""

    def __init__(
        self,
        status_filters: list[str] | None = None,
        project_filters: list[str] | None = None,
        model_size_override: Literal["little", "big"] | None = None,
        refresh_interval: int = 15,
    ) -> None:
        """Initialize the work workflow.

        Args:
            status_filters: List of status values to filter by (OR logic)
            project_filters: List of project basenames to filter by (OR logic)
            model_size_override: Override model size for all GeminiCommandWrapper instances
            refresh_interval: Auto-refresh interval in seconds (0 to disable, default: 15)
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

    def _handle_add_hook(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle 'h' (add hook) action.

        Args:
            changespec: Current ChangeSpec
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        return handle_add_hook(self, changespec, changespecs, current_idx)

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

    def _handle_refresh(
        self, changespec: ChangeSpec, changespecs: list[ChangeSpec], current_idx: int
    ) -> tuple[list[ChangeSpec], int]:
        """Handle 'y' (refresh) action - rescan project files.

        Rescans project files to refresh the list of ChangeSpecs based on
        the current filter flags (-s and -p).

        Args:
            changespec: Current ChangeSpec (used for repositioning after refresh)
            changespecs: List of all changespecs
            current_idx: Current index

        Returns:
            Tuple of (updated_changespecs, updated_index)
        """
        self.console.print("[cyan]Refreshing ChangeSpec list...[/cyan]")

        # Reload changespecs from disk and apply filters
        changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

        self.console.print(f"[green]Found {len(changespecs)} ChangeSpec(s)[/green]")
        return changespecs, current_idx

    def _handle_view(self, changespec: ChangeSpec) -> None:
        """Handle 'v' (view files) action.

        Displays the ChangeSpec with numbered hints next to file paths,
        prompts user to select files, and displays them using bat/cat.
        If the last hint ends with '@', opens all selected files in $EDITOR.

        Args:
            changespec: Current ChangeSpec
        """
        import shutil
        import subprocess

        # Re-display with hints enabled
        self.console.clear()
        hint_mappings = display_changespec(changespec, self.console, with_hints=True)

        if not hint_mappings:
            self.console.print("[yellow]No files available to view[/yellow]")
            return

        # Show available hints
        self.console.print()
        self.console.print(
            "[cyan]Enter hint numbers (space-separated) to view files.[/cyan]"
        )
        self.console.print(
            "[cyan]Use [0] to view the project file. "
            "Add '@' to last number (e.g., '3@') to open in $EDITOR.[/cyan]"
        )
        self.console.print()

        try:
            user_input = input("Hints: ").strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("\n[yellow]Cancelled[/yellow]")
            return

        if not user_input:
            return

        # Parse hint numbers
        parts = user_input.split()
        if not parts:
            return

        open_in_editor = False
        hints_to_view: list[int] = []

        for part in parts:
            # Check for '@' suffix on the last part
            if part.endswith("@"):
                open_in_editor = True
                part = part[:-1]

            try:
                hint_num = int(part)
                if hint_num in hint_mappings:
                    hints_to_view.append(hint_num)
                else:
                    self.console.print(f"[yellow]Invalid hint: {hint_num}[/yellow]")
            except ValueError:
                self.console.print(f"[yellow]Invalid input: {part}[/yellow]")

        if not hints_to_view:
            return

        # Collect file paths and expand ~ to home directory
        files_to_view = [os.path.expanduser(hint_mappings[h]) for h in hints_to_view]

        if open_in_editor:
            # Open in $EDITOR
            editor = os.environ.get("EDITOR", "vi")
            try:
                subprocess.run([editor] + files_to_view, check=False)
            except FileNotFoundError:
                self.console.print(f"[red]Editor not found: {editor}[/red]")
        else:
            # Display using bat or cat
            viewer = "bat" if shutil.which("bat") else "cat"
            try:
                subprocess.run([viewer] + files_to_view, check=False)
            except FileNotFoundError:
                self.console.print(f"[red]Viewer not found: {viewer}[/red]")

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
                _wait_for_user_input()
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

            # Get user input with optional timeout for auto-refresh
            # Note: Don't lowercase - we need to distinguish 'r' (run workflow) from 'R' (run query)
            try:
                user_input, pending_input = _input_with_timeout(
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
            elif user_input == "h":
                changespecs, current_idx = self._handle_add_hook(
                    changespec, changespecs, current_idx
                )
                # No wait needed - displays inline message
            elif user_input == "R":
                self._handle_run_query(changespec)
                should_wait_before_clear = True  # Query output needs to be read
            elif user_input == "v":
                self._handle_view(changespec)
                should_wait_before_clear = True  # View output needs to be read
            elif user_input == "y":
                changespecs, current_idx = self._handle_refresh(
                    changespec, changespecs, current_idx
                )
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
        if changespec.cl is not None:
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

        def _get_workflow_label(name: str) -> str:
            """Get the display label for a workflow name."""
            return name

        workflows = get_available_workflows(changespec)
        if len(workflows) == 1:
            label = _get_workflow_label(workflows[0])
            options_with_keys.append(
                (make_sort_key("r"), format_option("r", f"run {label}", False))
            )
        elif len(workflows) > 1:
            for i, workflow_name in enumerate(workflows, start=1):
                key = f"r{i}"
                label = _get_workflow_label(workflow_name)
                options_with_keys.append(
                    (
                        make_sort_key(key),
                        format_option(key, f"run {label}", False),
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

        # Show add hook option
        options_with_keys.append(
            (make_sort_key("h"), format_option("h", "add hook", False))
        )

        # View files option is always available
        options_with_keys.append(
            (make_sort_key("v"), format_option("v", "view", False))
        )

        # Refresh option is always available - rescans project files
        options_with_keys.append(
            (make_sort_key("y"), format_option("y", "refresh", False))
        )

        # Sort by the sort key and return just the formatted strings
        options_with_keys.sort(key=lambda x: x[0])
        return [opt[1] for opt in options_with_keys]

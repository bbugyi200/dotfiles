"""Rewind workflow methods for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...widgets import HintInputBar
from ._types import HintMixinBase

if TYPE_CHECKING:
    from ....changespec import ChangeSpec


class RewindMixin(HintMixinBase):
    """Mixin providing rewind workflow actions."""

    # Type hints for attributes accessed from AceApp
    _rewind_mode_active: bool

    def action_start_rewind(self) -> None:
        """Start rewind mode - prompt user to select entry to rewind to."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Check if there are at least 2 all-numeric COMMITS entries
        # (we need an entry after the selected one)
        numeric_entries = [e for e in (changespec.commits or []) if not e.is_proposed]
        if len(numeric_entries) < 2:
            self.notify(  # type: ignore[attr-defined]
                "Need at least 2 accepted commits to rewind",
                severity="warning",
            )
            return

        # Build placeholder with available entry numbers (excluding the last one)
        # since you can't rewind to the last entry
        available_nums = sorted([e.number for e in numeric_entries])
        # All but the last can be selected
        selectable_nums = available_nums[:-1]
        placeholder = f"Enter entry number to rewind to ({selectable_nums[0]}-{selectable_nums[-1]})"

        # Store rewind mode state
        self._rewind_mode_active = True

        # Mount the rewind input bar
        detail_container = self.query_one("#detail-container")  # type: ignore[attr-defined]
        rewind_bar = HintInputBar(
            mode="rewind", placeholder=placeholder, id="hint-input-bar"
        )
        detail_container.mount(rewind_bar)

    def _process_rewind_input(self, user_input: str) -> None:
        """Process the selected entry number for rewind.

        Args:
            user_input: The user's input (should be an all-numeric entry number).
        """
        if not user_input:
            return

        changespec = self.changespecs[self.current_idx]

        # Parse and validate entry number
        try:
            selected_entry_num = int(user_input.strip())
        except ValueError:
            self.notify(  # type: ignore[attr-defined]
                f"Invalid entry number: {user_input}",
                severity="warning",
            )
            return

        # Validate entry exists and is all-numeric (accepted)
        numeric_entries = [e for e in (changespec.commits or []) if not e.is_proposed]
        entry_nums = {e.number for e in numeric_entries}

        if selected_entry_num not in entry_nums:
            self.notify(  # type: ignore[attr-defined]
                f"Entry ({selected_entry_num}) not found or is a proposal",
                severity="warning",
            )
            return

        # Validate there's at least one all-numeric entry AFTER the selected one
        entries_after = [e for e in numeric_entries if e.number > selected_entry_num]
        if not entries_after:
            self.notify(  # type: ignore[attr-defined]
                f"No entries after ({selected_entry_num}) - cannot rewind to last entry",
                severity="warning",
            )
            return

        # Validate selected entry has a DIFF file
        selected_entry = next(
            (e for e in numeric_entries if e.number == selected_entry_num), None
        )
        if not selected_entry or not selected_entry.diff:
            self.notify(  # type: ignore[attr-defined]
                f"Entry ({selected_entry_num}) has no DIFF path",
                severity="warning",
            )
            return

        # Run rewind workflow
        self._run_rewind_workflow(changespec, selected_entry_num)

    def _run_rewind_workflow(
        self, changespec: ChangeSpec, selected_entry_num: int
    ) -> None:
        """Execute the rewind workflow.

        Args:
            changespec: The ChangeSpec to rewind.
            selected_entry_num: The entry number to rewind to.
        """
        from rewind_workflow import RewindWorkflow

        def run_handler() -> tuple[bool, str]:
            workflow = RewindWorkflow(
                cl_name=changespec.name,
                project_file=changespec.file_path,
                selected_entry_num=selected_entry_num,
            )
            return workflow.run()

        self.notify(f"Rewinding to entry ({selected_entry_num})...")  # type: ignore[attr-defined]

        with self.suspend():  # type: ignore[attr-defined]
            success, message = run_handler()

        if success:
            self.notify(message)  # type: ignore[attr-defined]
        else:
            self.notify(f"Rewind failed: {message}", severity="error")  # type: ignore[attr-defined]

        self._reload_and_reposition()  # type: ignore[attr-defined]

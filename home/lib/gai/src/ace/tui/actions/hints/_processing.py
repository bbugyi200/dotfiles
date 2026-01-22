"""Event handlers and input processing for the ace TUI app."""

from __future__ import annotations

from ....hint_types import EditHooksResult, ViewFilesResult
from ....hints import (
    is_rerun_input,
    parse_edit_hooks_input,
    parse_test_targets,
    parse_view_input,
)
from ...widgets import HintInputBar
from ._types import HintMixinBase


class InputProcessingMixin(HintMixinBase):
    """Mixin providing input processing for hint modes."""

    def on_hint_input_bar_submitted(self, event: HintInputBar.Submitted) -> None:
        """Handle hint input submission."""
        self._remove_hint_input_bar()

        if event.mode == "view":
            self._process_view_input(event.value)
        elif event.mode == "hooks":
            self._process_hooks_input(event.value)
        elif event.mode == "failed_hooks":
            self._process_failed_hooks_input(event.value)
        elif event.mode == "copy":
            self._process_copy_input(event.value)  # type: ignore[attr-defined]
        else:  # accept mode
            self._process_accept_input(event.value)  # type: ignore[attr-defined]

    def on_hint_input_bar_cancelled(self, event: HintInputBar.Cancelled) -> None:
        """Handle hint input cancellation."""
        del event  # unused
        self._remove_hint_input_bar()

    def _remove_hint_input_bar(self) -> None:
        """Remove the hint input bar and restore normal display."""
        # Clear hint mode state first
        self._hint_mode_active = False
        self._hint_mode_hints_for = None

        # Clear accept mode state
        self._accept_mode_active = False

        try:
            hint_bar = self.query_one("#hint-input-bar", HintInputBar)  # type: ignore[attr-defined]
            hint_bar.remove()
        except Exception:
            pass
        self._refresh_display()  # type: ignore[attr-defined]

    def _process_view_input(self, user_input: str) -> None:
        """Process view files input."""
        if not user_input:
            return

        files, open_in_editor, copy_to_clipboard, invalid_hints = parse_view_input(
            user_input, self._hint_mappings
        )

        if invalid_hints:
            self.notify(  # type: ignore[attr-defined]
                f"Invalid hints: {', '.join(str(h) for h in invalid_hints)}",
                severity="warning",
            )
            return

        if not files:
            self.notify("No valid files selected", severity="warning")  # type: ignore[attr-defined]
            return

        if copy_to_clipboard:
            self._copy_files_to_clipboard(files)  # type: ignore[attr-defined]
        elif open_in_editor:
            result = ViewFilesResult(
                files=files,
                open_in_editor=True,
                copy_to_clipboard=False,
                user_input=user_input,
                changespec_name=self._hint_changespec_name,
            )
            self._open_files_in_editor(result)  # type: ignore[attr-defined]
        else:
            self._view_files_with_pager(files)  # type: ignore[attr-defined]

    def _process_hooks_input(self, user_input: str) -> None:
        """Process edit hooks input."""
        if not user_input:
            return

        changespec = self.changespecs[self.current_idx]

        if is_rerun_input(user_input):
            # Rerun/delete hooks
            hints_to_rerun, hints_to_delete, invalid_hints = parse_edit_hooks_input(
                user_input, self._hint_mappings
            )

            if invalid_hints:
                self.notify(  # type: ignore[attr-defined]
                    f"Invalid hints: {', '.join(str(h) for h in invalid_hints)}",
                    severity="warning",
                )
                return

            if not hints_to_rerun and not hints_to_delete:
                self.notify("No valid hooks selected", severity="warning")  # type: ignore[attr-defined]
                return

            result = EditHooksResult(
                action_type="rerun_delete",
                hints_to_rerun=hints_to_rerun,
                hints_to_delete=hints_to_delete,
            )
            success = self._apply_hook_changes(  # type: ignore[attr-defined]
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()  # type: ignore[attr-defined]

        elif user_input.startswith("//"):
            # Test targets
            targets = parse_test_targets(user_input)
            if not targets:
                self.notify("No test targets provided", severity="warning")  # type: ignore[attr-defined]
                return

            result = EditHooksResult(
                action_type="test_targets",
                test_targets=targets,
            )
            success = self._apply_hook_changes(  # type: ignore[attr-defined]
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()  # type: ignore[attr-defined]

        else:
            # Custom hook command
            result = EditHooksResult(
                action_type="custom_hook",
                hook_command=user_input,
            )
            success = self._apply_hook_changes(  # type: ignore[attr-defined]
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()  # type: ignore[attr-defined]

    def _process_failed_hooks_input(self, user_input: str) -> None:
        """Process failed hooks input to add selected targets as hooks.

        Input can be:
        - Single numbers: "1", "2", "3"
        - Space-separated: "1 3 5"
        - Ranges: "1-5"
        - Mixed: "1 3-5 7"
        """
        if not user_input:
            return

        changespec = self.changespecs[self.current_idx]
        targets = getattr(self, "_failed_hooks_targets", [])

        if not targets:
            self.notify("No targets available", severity="warning")  # type: ignore[attr-defined]
            return

        # Parse the input to get selected indices (1-based)
        selected_indices: set[int] = set()
        invalid_parts: list[str] = []

        parts = user_input.split()
        for part in parts:
            if "-" in part and not part.startswith("-"):
                # Range like "1-5"
                try:
                    start_str, end_str = part.split("-", 1)
                    start = int(start_str)
                    end = int(end_str)
                    for i in range(start, end + 1):
                        if 1 <= i <= len(targets):
                            selected_indices.add(i)
                        else:
                            invalid_parts.append(str(i))
                except ValueError:
                    invalid_parts.append(part)
            else:
                # Single number
                try:
                    idx = int(part)
                    if 1 <= idx <= len(targets):
                        selected_indices.add(idx)
                    else:
                        invalid_parts.append(part)
                except ValueError:
                    invalid_parts.append(part)

        if invalid_parts:
            self.notify(  # type: ignore[attr-defined]
                f"Invalid selections: {', '.join(invalid_parts)}",
                severity="warning",
            )
            return

        if not selected_indices:
            self.notify("No valid targets selected", severity="warning")  # type: ignore[attr-defined]
            return

        # Get the selected targets (convert 1-based to 0-based)
        selected_targets = [targets[i - 1] for i in sorted(selected_indices)]

        # Add them as hooks
        success = self._add_test_target_hooks(changespec, selected_targets)  # type: ignore[attr-defined]
        if success:
            self._reload_and_reposition()  # type: ignore[attr-defined]

"""Edit hooks modal for the ace TUI."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ...hint_types import EditHooksResult, HintItem
from ...hints import is_rerun_input, parse_edit_hooks_input, parse_test_targets


class _HookInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class EditHooksModal(ModalScreen[EditHooksResult | None]):
    """Modal for editing hooks - rerun, delete, or add new."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        hints: list[HintItem],
        hint_mappings: dict[int, str],
        hook_hint_to_idx: dict[int, int],
    ) -> None:
        """Initialize the edit hooks modal.

        Args:
            hints: List of HintItem objects to display
            hint_mappings: Dict mapping hint numbers to file paths
            hook_hint_to_idx: Dict mapping hint numbers to hook indices
        """
        super().__init__()
        self.hints = hints
        self.hint_mappings = hint_mappings
        self.hook_hint_to_idx = hook_hint_to_idx

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="edit-hooks-container"):
            yield Label("Edit Hooks", id="modal-title")
            if self.hints:
                yield Static(self._build_hints_display(), id="hints-display")
            yield Static(self._build_instructions(), id="instructions")
            yield _HookInput(placeholder="1 2@ or //target or command", id="hook-input")
            yield Static("", id="error-message")
            with Horizontal(id="button-row"):
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel", variant="default")

    def _build_hints_display(self) -> Text:
        """Build Rich Text display of available hints."""
        text = Text()
        for item in self.hints:
            # Color based on status in display text
            status_style = "#87AFFF"  # Default blue
            if "[PASSED]" in item.display_text:
                status_style = "#00AF00"  # Green
            elif "[FAILED]" in item.display_text:
                status_style = "#FF5F5F"  # Red
            elif "[RUNNING]" in item.display_text:
                status_style = "#87AFFF"  # Blue
            elif "[ZOMBIE]" in item.display_text:
                status_style = "#FFAF00"  # Orange

            text.append(f"[{item.hint_number}] ", style="bold #FFFF00")
            text.append(f"{item.display_text}\n", style=status_style)
        # Remove trailing newline
        text.rstrip()
        return text

    def _build_instructions(self) -> Text:
        """Build instructions text."""
        text = Text()
        if self.hints:
            text.append("- Enter hint numbers to rerun hooks\n", style="#808080")
            text.append("- Add '@' suffix to delete (e.g., '2@')\n", style="#808080")
        text.append("- Enter '//target' to add bb_rabbit_test hooks\n", style="#808080")
        text.append("- Enter any other text to add as a hook command", style="#808080")
        return text

    def on_mount(self) -> None:
        """Focus the input on mount."""
        hook_input = self.query_one("#hook-input", _HookInput)
        hook_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "apply":
            self._submit_input()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self._submit_input()

    def _submit_input(self) -> None:
        """Process and submit the user input."""
        hook_input = self.query_one("#hook-input", Input)
        user_input = hook_input.value.strip()

        if not user_input:
            self.dismiss(None)
            return

        # Determine what type of input this is
        if is_rerun_input(user_input):
            # Rerun/delete hooks
            hints_to_rerun, hints_to_delete, invalid_hints = parse_edit_hooks_input(
                user_input, self.hint_mappings
            )

            if invalid_hints:
                error_msg = self.query_one("#error-message", Static)
                error_msg.update(
                    Text(
                        f"Invalid hints: {', '.join(str(h) for h in invalid_hints)}",
                        style="red",
                    )
                )
                return

            if not hints_to_rerun and not hints_to_delete:
                error_msg = self.query_one("#error-message", Static)
                error_msg.update(Text("No valid hooks selected", style="red"))
                return

            self.dismiss(
                EditHooksResult(
                    action_type="rerun_delete",
                    hints_to_rerun=hints_to_rerun,
                    hints_to_delete=hints_to_delete,
                )
            )

        elif user_input.startswith("//"):
            # Test targets
            targets = parse_test_targets(user_input)
            if not targets:
                error_msg = self.query_one("#error-message", Static)
                error_msg.update(Text("No test targets provided", style="red"))
                return

            self.dismiss(
                EditHooksResult(
                    action_type="test_targets",
                    test_targets=targets,
                )
            )

        else:
            # Custom hook command
            self.dismiss(
                EditHooksResult(
                    action_type="custom_hook",
                    hook_command=user_input,
                )
            )

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)

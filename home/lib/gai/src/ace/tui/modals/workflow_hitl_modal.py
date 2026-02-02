"""Workflow HITL modal for the ace TUI."""

from dataclasses import dataclass
from typing import Any

from rich.syntax import Syntax
from shared_utils import dump_yaml
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static
from xprompt import HITLResult


@dataclass
class WorkflowHITLInput:
    """Input data for the HITL modal."""

    step_name: str
    step_type: str  # "agent", "bash", or "python"
    output: Any
    workflow_name: str
    has_output: bool = False  # Whether step has output field defined


class WorkflowHITLModal(ModalScreen[HITLResult | None]):
    """Modal for human-in-the-loop review of workflow step output."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("a", "accept", "Accept"),
        ("x", "reject", "Reject"),
        ("e", "edit", "Edit"),  # Agent steps only
        ("r", "rerun", "Rerun"),  # Bash steps only
    ]

    def __init__(self, input_data: WorkflowHITLInput) -> None:
        """Initialize the HITL modal.

        Args:
            input_data: The HITL input data containing step info and output.
        """
        super().__init__()
        self.input_data = input_data

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="hitl-container"):
            yield Label(
                "[bold cyan]Workflow Step Review[/bold cyan]",
                id="modal-title",
            )
            yield Label(
                f"Step: {self.input_data.step_name} ({self.input_data.step_type})",
                id="step-info",
            )

            # Output preview
            with ScrollableContainer(id="output-preview"):
                if isinstance(self.input_data.output, dict):
                    display_data = self.input_data.output.get(
                        "_data", self.input_data.output
                    )
                    output_str = dump_yaml(display_data, sort_keys=False)
                else:
                    output_str = str(self.input_data.output)
                syntax = Syntax(output_str, "yaml", theme="monokai", word_wrap=True)
                yield Static(syntax, id="output-content")

            # Action hints
            # Edit option for agent steps, or bash/python with output field
            can_edit = self.input_data.step_type == "agent" or (
                self.input_data.step_type in ("bash", "python")
                and self.input_data.has_output
            )
            action_hints = "[green]a[/green]=Accept  [red]x[/red]=Reject"
            if can_edit:
                action_hints += "  [yellow]e[/yellow]=Edit"
            if self.input_data.step_type in ("bash", "python"):
                action_hints += "  [yellow]r[/yellow]=Rerun"

            yield Label(action_hints, id="action-hints")

            # Buttons
            with Horizontal(id="button-row"):
                yield Button("Accept (a)", id="accept-btn", variant="success")
                yield Button("Reject (x)", id="reject-btn", variant="error")
                if can_edit:
                    yield Button("Edit (e)", id="edit-btn", variant="warning")
                if self.input_data.step_type in ("bash", "python"):
                    yield Button("Rerun (r)", id="rerun-btn", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "accept-btn":
            self.action_accept()
        elif event.button.id == "reject-btn":
            self.action_reject()
        elif event.button.id == "edit-btn":
            self.action_edit()
        elif event.button.id == "rerun-btn":
            self.action_rerun()

    def action_cancel(self) -> None:
        """Cancel/reject the modal."""
        self.dismiss(HITLResult(action="reject", approved=False))

    def action_accept(self) -> None:
        """Accept the step output."""
        self.dismiss(HITLResult(action="accept", approved=True))

    def action_reject(self) -> None:
        """Reject and abort the workflow."""
        self.dismiss(HITLResult(action="reject", approved=False))

    def action_edit(self) -> None:
        """Edit the step output (agent steps or bash/python with output field)."""
        can_edit = self.input_data.step_type == "agent" or (
            self.input_data.step_type in ("bash", "python")
            and self.input_data.has_output
        )
        if can_edit:
            self.dismiss(HITLResult(action="edit"))

    def action_rerun(self) -> None:
        """Rerun the step (bash/python steps only)."""
        if self.input_data.step_type in ("bash", "python"):
            self.dismiss(HITLResult(action="rerun"))

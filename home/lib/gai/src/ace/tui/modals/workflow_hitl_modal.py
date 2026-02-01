"""Workflow HITL modal for the ace TUI."""

import json
from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static
from xprompt import HITLResult


@dataclass
class WorkflowHITLInput:
    """Input data for the HITL modal."""

    step_name: str
    step_type: str  # "agent" or "bash"
    output: Any
    workflow_name: str


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
                    output_str = json.dumps(self.input_data.output, indent=2)
                else:
                    output_str = str(self.input_data.output)
                yield Static(output_str, id="output-content")

            # Action hints
            action_hints = "[green]a[/green]=Accept  [red]x[/red]=Reject"
            if self.input_data.step_type == "agent":
                action_hints += "  [yellow]e[/yellow]=Edit"
            elif self.input_data.step_type == "bash":
                action_hints += "  [yellow]r[/yellow]=Rerun"

            yield Label(action_hints, id="action-hints")

            # Buttons
            with Horizontal(id="button-row"):
                yield Button("Accept (a)", id="accept-btn", variant="success")
                yield Button("Reject (x)", id="reject-btn", variant="error")
                if self.input_data.step_type == "agent":
                    yield Button("Edit (e)", id="edit-btn", variant="warning")
                elif self.input_data.step_type == "bash":
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
        """Edit the step output (agent steps only)."""
        if self.input_data.step_type == "agent":
            self.dismiss(HITLResult(action="edit"))

    def action_rerun(self) -> None:
        """Rerun the step (bash steps only)."""
        if self.input_data.step_type == "bash":
            self.dismiss(HITLResult(action="rerun"))

"""Workflow HITL modal for the ace TUI."""

import os
from dataclasses import dataclass, field
from typing import Any

from rich.syntax import Syntax
from shared_utils import dump_yaml
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static
from xprompt import HITLResult

from .base import CopyModeForwardingMixin

_EXTENSION_TO_LEXER: dict[str, str] = {
    ".diff": "diff",
    ".patch": "diff",
    ".py": "python",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sh": "bash",
    ".bash": "bash",
    ".js": "javascript",
    ".ts": "typescript",
    ".md": "markdown",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
}


@dataclass
class WorkflowHITLInput:
    """Input data for the HITL modal."""

    step_name: str
    step_type: str  # "agent", "bash", or "python"
    output: Any
    workflow_name: str
    has_output: bool = False  # Whether step has output field defined
    output_types: dict[str, str] = field(default_factory=dict)


class WorkflowHITLModal(CopyModeForwardingMixin, ModalScreen[HITLResult | None]):
    """Modal for human-in-the-loop review of workflow step output."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("a", "accept", "Accept"),
        ("x", "reject", "Reject"),
        ("e", "edit", "Edit"),  # Agent steps only
        ("r", "rerun", "Rerun"),  # Bash steps only
        ("ctrl+d", "scroll_down", "Scroll down"),
        ("ctrl+u", "scroll_up", "Scroll up"),
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
        path_files = self._get_path_files()

        # Build footer hints
        can_edit = self.input_data.step_type == "agent" or (
            self.input_data.step_type in ("bash", "python")
            and self.input_data.has_output
        )
        hints = "[green]a[/green]=Accept  [red]x[/red]=Reject"
        if can_edit:
            hints += "  [yellow]e[/yellow]=Edit"
        if self.input_data.step_type in ("bash", "python"):
            hints += "  [yellow]r[/yellow]=Rerun"
        hints += "  |  Ctrl+D/U to scroll"

        with Container(id="hitl-container"):
            yield Static(
                "[bold cyan]Workflow Step Review[/bold cyan]",
                id="hitl-title",
            )

            with VerticalScroll(id="hitl-content-scroll"):
                yield Static(
                    f"Step: {self.input_data.step_name} ({self.input_data.step_type})",
                    id="step-info",
                )

                # Output section
                yield Static("[bold]Output:[/bold]", classes="hitl-section-header")
                if isinstance(self.input_data.output, dict):
                    display_data = self.input_data.output.get(
                        "_data", self.input_data.output
                    )
                    output_str = dump_yaml(display_data, sort_keys=False)
                else:
                    output_str = str(self.input_data.output)
                syntax = Syntax(output_str, "yaml", theme="monokai", word_wrap=True)
                yield Static(syntax, id="output-content")

                # File content sections for path-typed fields
                for field_name, file_path, content, lexer in path_files:
                    yield Static(
                        f"[bold green]{field_name}:[/bold green] {file_path}",
                        classes="hitl-section-header",
                    )
                    file_syntax = Syntax(
                        content, lexer, theme="monokai", word_wrap=True
                    )
                    yield Static(file_syntax)

            yield Static(hints, id="hitl-footer")

    def _get_path_files(self) -> list[tuple[str, str, str, str]]:
        """Get file contents for path-typed output fields.

        Returns:
            List of (field_name, file_path, content, lexer) tuples.
        """
        result: list[tuple[str, str, str, str]] = []
        if not self.input_data.output_types or not isinstance(
            self.input_data.output, dict
        ):
            return result
        for field_name, field_type in self.input_data.output_types.items():
            if field_type != "path":
                continue
            path_value = self.input_data.output.get(field_name)
            if not path_value or not os.path.isfile(str(path_value)):
                continue
            file_path = str(path_value)
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = f"[Error reading file: {file_path}]"
            ext = os.path.splitext(file_path)[1].lower()
            lexer = _EXTENSION_TO_LEXER.get(ext, "text")
            result.append((field_name, file_path, content, lexer))
        return result

    def action_scroll_down(self) -> None:
        """Scroll the content down by half a page."""
        scroll = self.query_one("#hitl-content-scroll", VerticalScroll)
        height = scroll.scrollable_content_region.height
        scroll.scroll_relative(y=height // 2, animate=False)

    def action_scroll_up(self) -> None:
        """Scroll the content up by half a page."""
        scroll = self.query_one("#hitl-content-scroll", VerticalScroll)
        height = scroll.scrollable_content_region.height
        scroll.scroll_relative(y=-(height // 2), animate=False)

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

"""XPrompt selection modal with filtering for the ace TUI."""

from __future__ import annotations

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option
from xprompt import get_all_snippets, get_all_workflows
from xprompt.workflow_models import Workflow

from .base import OptionListNavigationMixin


class _XPromptFilterInput(Input):
    """Custom input for XPrompt modal with scroll key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
        ("ctrl+d", "scroll_preview_down", "Scroll Down"),
        ("ctrl+u", "scroll_preview_up_or_clear", "Scroll Up/Clear"),
    ]

    def action_scroll_preview_down(self) -> None:
        """Scroll the preview panel down."""
        modal = self.screen
        if isinstance(modal, XPromptSelectModal):
            modal.scroll_preview_down()

    def action_scroll_preview_up_or_clear(self) -> None:
        """Scroll preview up, or clear input if already at top."""
        modal = self.screen
        if isinstance(modal, XPromptSelectModal):
            scroll = modal.query_one("#xprompt-preview-scroll", VerticalScroll)
            if scroll.scroll_y > 0:
                modal.scroll_preview_up()
            elif self.cursor_position > 0:
                # At top - clear line (unix line discard behavior)
                self.value = self.value[self.cursor_position :]
                self.cursor_position = 0


class XPromptSelectModal(OptionListNavigationMixin, ModalScreen[str | None]):
    """Modal for selecting an xprompt with filtering and preview."""

    _option_list_id = "xprompt-list"
    BINDINGS = [*OptionListNavigationMixin.NAVIGATION_BINDINGS]

    def __init__(self) -> None:
        """Initialize the xprompt modal."""
        super().__init__()
        self.xprompts = get_all_snippets()
        self.workflows = get_all_workflows()
        # Build unified items dict: name -> (content/preview, type)
        self._all_items: dict[str, tuple[str, str]] = {}
        for name, content in self.xprompts.items():
            self._all_items[name] = (content, "xprompt")
        for name, workflow in self.workflows.items():
            preview = self._create_workflow_preview(workflow)
            self._all_items[name] = (preview, "workflow")
        self._filtered_names: list[str] = sorted(self._all_items.keys())

    def _create_workflow_preview(self, workflow: Workflow) -> str:
        """Create a preview string for a workflow.

        Args:
            workflow: The Workflow object.

        Returns:
            A preview string showing workflow details.
        """
        lines: list[str] = []
        lines.append(f"# Workflow: {workflow.name}")
        lines.append("")

        if workflow.inputs:
            lines.append("## Inputs")
            for inp in workflow.inputs:
                default_str = f" (default: {inp.default})" if inp.default else ""
                lines.append(f"- **{inp.name}**: {inp.type.value}{default_str}")
            lines.append("")

        lines.append("## Steps")
        for i, step in enumerate(workflow.steps, 1):
            step_type = "agent" if step.agent else "bash"
            step_label = step.agent if step.agent else step.bash
            lines.append(f"{i}. [{step_type}] {step.name}: {step_label}")

        return "\n".join(lines)

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="xprompt-modal-container"):
            yield Label("Select XPrompt", id="modal-title")
            if not self._all_items:
                yield Label("No xprompts configured")
            else:
                yield _XPromptFilterInput(
                    placeholder="Type to filter...", id="xprompt-filter-input"
                )
                with Horizontal(id="xprompt-panels"):
                    with Vertical(id="xprompt-list-panel"):
                        yield Label("XPrompts", id="xprompt-list-label")
                        yield OptionList(
                            *self._create_options(self._filtered_names),
                            id="xprompt-list",
                        )
                    with Vertical(id="xprompt-preview-panel"):
                        yield Label("Preview", id="xprompt-preview-label")
                        with VerticalScroll(id="xprompt-preview-scroll"):
                            yield Static("", id="xprompt-preview")
                yield Static(
                    "j/k ↑/↓: navigate • ^d/^u: scroll preview • Enter: select • Esc/q: cancel",
                    id="xprompt-hints",
                )

    def _create_styled_label(self, name: str) -> Text:
        """Create styled text for an xprompt or workflow name."""
        text = Text()
        item_type = self._all_items.get(name, ("", "xprompt"))[1]
        if item_type == "workflow":
            text.append("⚙ ", style="bold #FFD700")  # Gold gear for workflows
            text.append("#", style="bold #87D7FF")  # Cyan hash
            text.append(name)
        else:
            text.append("#", style="bold #87D7FF")  # Cyan hash
            text.append(name)
        return text

    def _create_options(self, names: list[str]) -> list[Option]:
        """Create options from xprompt names."""
        return [Option(self._create_styled_label(name), id=name) for name in names]

    def _get_filtered_names(self, filter_text: str) -> list[str]:
        """Get xprompt and workflow names that match the filter text."""
        all_names = sorted(self._all_items.keys())
        if not filter_text:
            return all_names
        filter_lower = filter_text.lower()
        return [name for name in all_names if filter_lower in name.lower()]

    def on_mount(self) -> None:
        """Focus the input and show initial preview on mount."""
        if self._all_items:
            filter_input = self.query_one("#xprompt-filter-input", _XPromptFilterInput)
            filter_input.focus()
            # Show preview for first item
            if self._filtered_names:
                self._update_preview_for_name(self._filtered_names[0])

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change - update the option list."""
        self._filtered_names = self._get_filtered_names(event.value)
        option_list = self.query_one("#xprompt-list", OptionList)
        option_list.clear_options()
        for option in self._create_options(self._filtered_names):
            option_list.add_option(option)
        # Update preview for first filtered item
        if self._filtered_names:
            self._update_preview_for_name(self._filtered_names[0])
        else:
            self._clear_preview()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle Enter key in input - select highlighted item."""
        if not self._filtered_names:
            return

        option_list = self.query_one("#xprompt-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None and 0 <= highlighted < len(self._filtered_names):
            self.dismiss(self._filtered_names[highlighted])
        else:
            # Select first item if none highlighted
            self.dismiss(self._filtered_names[0])

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Update preview when highlighting changes."""
        if event.option and event.option.id:
            self._update_preview_for_name(str(event.option.id))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))

    def scroll_preview_down(self) -> None:
        """Scroll preview panel down (half page)."""
        scroll = self.query_one("#xprompt-preview-scroll", VerticalScroll)
        height = scroll.scrollable_content_region.height
        scroll.scroll_relative(y=height // 2, animate=False)

    def scroll_preview_up(self) -> None:
        """Scroll preview panel up (half page)."""
        scroll = self.query_one("#xprompt-preview-scroll", VerticalScroll)
        height = scroll.scrollable_content_region.height
        scroll.scroll_relative(y=-(height // 2), animate=False)

    def _update_preview_for_name(self, name: str) -> None:
        """Update preview for an xprompt or workflow by name."""
        try:
            preview = self.query_one("#xprompt-preview", Static)
            item = self._all_items.get(name)
            if item:
                content, _ = item
            else:
                content = ""
            # Show raw content with markdown syntax highlighting
            syntax = Syntax(content, "markdown", theme="monokai", word_wrap=True)
            preview.update(syntax)
        except Exception:
            pass

    def _clear_preview(self) -> None:
        """Clear the preview panel."""
        try:
            preview = self.query_one("#xprompt-preview", Static)
            preview.update("")
        except Exception:
            pass


# Backward compatibility alias
SnippetSelectModal = XPromptSelectModal

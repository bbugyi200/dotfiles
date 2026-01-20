"""Process selection modal for the ace TUI.

Used when pressing X on non-AXE tabs with both axe and background commands running,
to select which process to stop.
"""

from dataclasses import dataclass
from typing import Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from ..bgcmd import BackgroundCommandInfo, is_slot_running
from .base import OptionListNavigationMixin


@dataclass
class ProcessSelection:
    """A process that can be selected for starting/stopping/dismissing."""

    process_type: Literal["axe", "bgcmd", "dismiss_bgcmd", "start_axe"]
    slot: int | None  # None for axe/start_axe, 1-9 for bgcmd/dismiss_bgcmd
    display_name: str
    description: str


class ProcessSelectModal(
    OptionListNavigationMixin, ModalScreen[ProcessSelection | None]
):
    """Modal for selecting which process to stop."""

    _option_list_id = "process-list"
    BINDINGS = [*OptionListNavigationMixin.NAVIGATION_BINDINGS]

    def __init__(
        self,
        axe_running: bool,
        bgcmd_slots: list[tuple[int, BackgroundCommandInfo]],
    ) -> None:
        """Initialize the process selection modal.

        Args:
            axe_running: Whether the axe daemon is running.
            bgcmd_slots: List of (slot, info) tuples for running background commands.
        """
        super().__init__()
        self._axe_running = axe_running
        self._bgcmd_slots = bgcmd_slots
        self._processes: list[ProcessSelection] = []
        self._build_process_list()

    def _build_process_list(self) -> None:
        """Build the list of processes that can be started/stopped."""
        # Add axe option (start or stop depending on state)
        if self._axe_running:
            self._processes.append(
                ProcessSelection(
                    process_type="axe",
                    slot=None,
                    display_name="gai axe",
                    description="Stop the axe scheduler daemon",
                )
            )
        else:
            self._processes.append(
                ProcessSelection(
                    process_type="start_axe",
                    slot=None,
                    display_name="gai axe",
                    description="Start the axe scheduler daemon",
                )
            )

        # Add background commands (running or done)
        for slot, info in self._bgcmd_slots:
            # Truncate command if too long
            cmd_display = info.command
            if len(cmd_display) > 40:
                cmd_display = cmd_display[:37] + "..."

            running = is_slot_running(slot)
            self._processes.append(
                ProcessSelection(
                    process_type="bgcmd" if running else "dismiss_bgcmd",
                    slot=slot,
                    display_name=cmd_display,
                    description=f"{info.project} (ws {info.workspace_num})",
                )
            )

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("AXE Control", id="modal-title")
            yield Label(
                "Select an action. Press Enter to confirm.",
                id="process-hint",
            )
            yield OptionList(
                *self._create_options(),
                id="process-list",
            )

    def _create_styled_label(self, process: ProcessSelection) -> Text:
        """Create styled text for a process option."""
        text = Text()

        if process.process_type == "start_axe":
            text.append("[START]", style="bold #00FF00")  # Green for start
            text.append("   ", style="")  # Extra space to align with [DISMISS]
            text.append(process.display_name, style="bold")
        elif process.process_type == "axe":
            text.append("[STOP]", style="bold #FFD700")  # Gold for axe stop
            text.append("    ", style="")  # Extra space to align with [DISMISS]
            text.append(process.display_name, style="bold")
        elif process.process_type == "bgcmd":
            text.append("[STOP]", style="bold #00D7AF")  # Cyan for running bgcmd
            text.append("    ", style="")  # Extra space to align with [DISMISS]
            text.append(process.display_name, style="")
        else:  # dismiss_bgcmd
            text.append("[DISMISS]", style="bold #FFD700")  # Gold for done bgcmd
            text.append(" ", style="")
            text.append(process.display_name, style="dim")

        text.append("\n", style="")
        text.append("          ", style="")  # Indent description
        text.append(process.description, style="dim")

        return text

    def _create_options(self) -> list[Option]:
        """Create options from processes."""
        return [
            Option(self._create_styled_label(proc), id=str(i))
            for i, proc in enumerate(self._processes)
        ]

    def on_mount(self) -> None:
        """Focus the option list on mount."""
        option_list = self.query_one("#process-list", OptionList)
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (Enter or click)."""
        if event.option and event.option.id is not None:
            idx = int(event.option.id)
            if 0 <= idx < len(self._processes):
                self.dismiss(self._processes[idx])

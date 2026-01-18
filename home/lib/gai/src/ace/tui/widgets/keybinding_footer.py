"""Keybinding footer widget for the ace TUI."""

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from ...changespec import ChangeSpec, has_ready_to_mail_suffix
from ...operations import get_available_workflows

if TYPE_CHECKING:
    from ..models.agent import Agent


class KeybindingFooter(Horizontal):
    """Footer showing available keybindings with status indicator on the right."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the footer widget."""
        super().__init__(**kwargs)
        self._axe_running: bool = False
        self._axe_starting: bool = False
        self._axe_stopping: bool = False
        self._bgcmd_count: int = 0

    def compose(self) -> ComposeResult:
        """Compose the footer with bindings on left and status on right."""
        yield Static(id="keybinding-content")
        yield Static(id="keybinding-status")

    def set_axe_running(self, running: bool) -> None:
        """Update the axe running state for binding labels.

        Args:
            running: Whether axe daemon is currently running.
        """
        self._axe_running = running
        self._update_status()

    def set_axe_starting(self, starting: bool) -> None:
        """Update the axe starting state.

        Args:
            starting: Whether axe daemon is currently starting.
        """
        self._axe_starting = starting
        self._update_status()

    def set_axe_stopping(self, stopping: bool) -> None:
        """Update the axe stopping state.

        Args:
            stopping: Whether axe daemon is currently stopping.
        """
        self._axe_stopping = stopping
        self._update_status()

    def set_bgcmd_count(self, count: int) -> None:
        """Update the background command count.

        Args:
            count: Number of running background commands.
        """
        self._bgcmd_count = count
        self._update_status()

    def _update_status(self) -> None:
        """Update the status indicator widget."""
        try:
            status = self.query_one("#keybinding-status", Static)
            status.update(self._get_status_text())
        except Exception:
            pass

    def _get_status_text(self) -> Text:
        """Get styled status indicator text.

        Returns:
            Formatted Text object for the status indicator.
        """
        text = Text()
        if self._axe_starting:
            text.append(" STARTING ", style="bold black on rgb(255,255,0)")
        elif self._axe_stopping:
            text.append(" STOPPING ", style="bold black on rgb(255,165,0)")
        elif self._axe_running:
            text.append(" RUNNING ", style="bold black on green")
        else:
            text.append(" STOPPED ", style="bold white on red")

        # Add bgcmd count badge if there are background commands running
        if self._bgcmd_count > 0:
            text.append(" ")
            text.append(f" [+{self._bgcmd_count}] ", style="bold black on #00D7AF")

        return text

    def _update_display(self, bindings_text: Text) -> None:
        """Update both the bindings content and status indicator.

        Args:
            bindings_text: Formatted text for the keybindings.
        """
        try:
            content = self.query_one("#keybinding-content", Static)
            status = self.query_one("#keybinding-status", Static)
            content.update(bindings_text)
            status.update(self._get_status_text())
        except Exception:
            pass

    def update_bindings(
        self,
        changespec: ChangeSpec,
        hidden_reverted_count: int = 0,
        hide_reverted: bool = True,
    ) -> None:
        """Update bindings based on current context.

        Args:
            changespec: Current ChangeSpec
            hidden_reverted_count: Number of hidden reverted ChangeSpecs
            hide_reverted: Whether reverted CLs are currently hidden
        """
        bindings = self._compute_available_bindings(
            changespec, hidden_reverted_count, hide_reverted
        )
        text = self._format_bindings(bindings)
        self._update_display(text)

    def show_empty(self) -> None:
        """Show empty state bindings."""
        text = Text()
        text.append("/", style="bold #00D7AF")
        text.append(" edit query", style="dim")
        self._update_display(text)

    def update_agent_bindings(
        self,
        agent: "Agent | None",
        *,
        diff_visible: bool = False,
        has_run_agents: bool = False,
        hidden_non_run_count: int = 0,
        hide_non_run: bool = True,
    ) -> None:
        """Update bindings for Agents tab context.

        Args:
            agent: Current Agent or None if no agents
            diff_visible: Whether the diff panel is currently visible
            has_run_agents: Whether any [run] agents exist
            hidden_non_run_count: Number of hidden non-run agents
            hide_non_run: Whether non-run agents are currently hidden
        """
        bindings = self._compute_agent_bindings(
            agent,
            diff_visible=diff_visible,
            has_run_agents=has_run_agents,
            hidden_non_run_count=hidden_non_run_count,
            hide_non_run=hide_non_run,
        )
        text = self._format_bindings(bindings)
        self._update_display(text)

    def update_axe_bindings(self) -> None:
        """Update bindings for Axe tab context."""
        bindings = self._compute_axe_bindings()
        text = self._format_bindings(bindings)
        self._update_display(text)

    def _compute_axe_bindings(self) -> list[tuple[str, str]]:
        """Compute available bindings for Axe tab.

        Returns:
            List of (key, label) tuples.
        """
        return [("<space>", "run cmd"), ("x", "clear"), ("%", "copy")]

    def _compute_agent_bindings(
        self,
        agent: "Agent | None",
        *,
        diff_visible: bool = False,
        has_run_agents: bool = False,
        hidden_non_run_count: int = 0,
        hide_non_run: bool = True,
    ) -> list[tuple[str, str]]:
        """Compute available bindings for Agents tab.

        Args:
            agent: Current Agent or None
            diff_visible: Whether the diff panel is currently visible
            has_run_agents: Whether any [run] agents exist
            hidden_non_run_count: Number of hidden non-run agents
            hide_non_run: Whether non-run agents are currently hidden

        Returns:
            List of (key, label) tuples
        """
        bindings: list[tuple[str, str]] = []

        # Kill/dismiss (only when agent selected)
        if agent is not None:
            if agent.status in ("NO CHANGES", "NEW CL", "NEW PROPOSAL", "REVIVED"):
                bindings.append(("x", "dismiss"))
                bindings.append(("@", "edit chat"))
                # Copy chat (only for completed/revived agents with chat available)
                if agent.response_path:
                    bindings.append(("%", "copy chat"))
            else:
                bindings.append(("x", "kill"))

        # Layout toggle (only when diff is visible)
        if diff_visible:
            bindings.append(("l", "layout"))

        # Run custom agent
        bindings.append(("<space>", "run agent"))

        # Revive chat as agent
        bindings.append(("r", "revive chat"))

        # Show/hide non-run agents (only when both run and non-run agents exist)
        if has_run_agents and (hidden_non_run_count > 0 or not hide_non_run):
            if hide_non_run:
                bindings.append((".", f"show ({hidden_non_run_count})"))
            else:
                bindings.append((".", "hide non-run"))

        return bindings

    def _compute_available_bindings(
        self,
        changespec: ChangeSpec,
        hidden_reverted_count: int = 0,
        hide_reverted: bool = True,
    ) -> list[tuple[str, str]]:
        """Compute available bindings based on current context.

        Args:
            changespec: Current ChangeSpec
            hidden_reverted_count: Number of hidden reverted ChangeSpecs
            hide_reverted: Whether reverted CLs are currently hidden

        Returns:
            List of (key, label) tuples
        """
        bindings: list[tuple[str, str]] = []

        # Accept proposal (only if proposed entries exist)
        if changespec.commits and any(e.is_proposed for e in changespec.commits):
            bindings.append(("a", "accept"))

        # Diff (only if CL exists)
        if changespec.cl is not None:
            bindings.append(("d", "diff"))

        # Get base status for visibility checks
        from ...changespec import get_base_status

        base_status = get_base_status(changespec.status)

        # Reword (only if CL exists AND status is Drafted or Mailed)
        if changespec.cl is not None:
            if base_status in ("Drafted", "Mailed"):
                bindings.append(("w", "reword"))

        # Mark ready to mail (only if Drafted without READY TO MAIL suffix)
        if base_status == "Drafted" and not has_ready_to_mail_suffix(changespec.status):
            bindings.append(("!", "ready"))

        # Mail (only if READY TO MAIL)
        if has_ready_to_mail_suffix(changespec.status):
            bindings.append(("m", "mail"))

        # Rebase (only if status is WIP, Drafted, or Mailed)
        if base_status in ("WIP", "Drafted", "Mailed"):
            bindings.append(("b", "rebase"))

        # Edit hooks
        bindings.append(("h", "hooks"))

        # Fold toggle
        bindings.append(("z", "fold (c,h,m,z)"))

        # Run workflows
        workflows = get_available_workflows(changespec)
        if len(workflows) == 1:
            bindings.append(("r", f"run {workflows[0]}"))
        elif len(workflows) > 1:
            bindings.append(("r", f"run ({len(workflows)} workflows)"))

        # Run agent (shift+space)
        bindings.append(("<S-space>", "run agent"))

        # Status change
        bindings.append(("s", "status"))

        # View files
        bindings.append(("v", "view"))

        # Edit query
        bindings.append(("/", "edit query"))

        # Edit spec
        bindings.append(("@", "edit spec"))

        # Copy ChangeSpec
        bindings.append(("%", "copy"))

        # Show/hide reverted toggle (only show if there are reverted to hide/show)
        if hidden_reverted_count > 0 or not hide_reverted:
            if hide_reverted:
                bindings.append((".", f"show ({hidden_reverted_count})"))
            else:
                bindings.append((".", "hide reverted"))

        return bindings

    def _format_bindings(self, bindings: list[tuple[str, str]]) -> Text:
        """Format bindings for display.

        Args:
            bindings: List of (key, label) tuples

        Returns:
            Formatted Text object
        """
        text = Text()

        # Sort bindings alphabetically (case-insensitive, lowercase before uppercase)
        # Put <space> or <S-space> first
        sorted_bindings = sorted(
            bindings,
            key=lambda x: (
                0 if x[0] in ("<space>", "<S-space>") else 1,
                x[0].lower(),
                x[0].isupper(),
                x[0],
            ),
        )

        for i, (key, label) in enumerate(sorted_bindings):
            if i > 0:
                text.append("  ")

            # Key in bold cyan
            text.append(key, style="bold #00D7AF")
            text.append(" ", style="")
            # Label in dim
            text.append(label, style="dim")

        return text

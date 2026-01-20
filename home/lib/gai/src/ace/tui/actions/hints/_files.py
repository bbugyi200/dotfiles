"""File viewing methods for the ace TUI app."""

from __future__ import annotations

import os
from pathlib import Path

from ....hint_types import ViewFilesResult
from ....hints import build_editor_args
from ...widgets import ChangeSpecDetail, HintInputBar
from ._types import HintMixinBase


class FileViewingMixin(HintMixinBase):
    """Mixin providing file viewing actions."""

    def action_view_files(self) -> None:
        """View files for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Re-render detail with hints
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        query_str = self.canonical_query_string  # type: ignore[attr-defined]
        hint_mappings, _, _ = detail_widget.update_display_with_hints(
            changespec,
            query_str,
            hints_for=None,
            hooks_collapsed=self.hooks_collapsed,  # type: ignore[attr-defined]
            commits_collapsed=self.commits_collapsed,  # type: ignore[attr-defined]
            mentors_collapsed=self.mentors_collapsed,  # type: ignore[attr-defined]
        )

        if not hint_mappings:  # No files available
            self.notify("No files available to view", severity="warning")  # type: ignore[attr-defined]
            self._refresh_display()  # type: ignore[attr-defined]
            return

        # Store state for later processing
        self._hint_mode_active = True
        self._hint_mode_hints_for = None  # "all" hints
        self._hint_mappings = hint_mappings
        self._hint_changespec_name = changespec.name

        # Mount the hint input bar
        detail_container = self.query_one("#detail-container")  # type: ignore[attr-defined]
        hint_bar = HintInputBar(mode="view", id="hint-input-bar")
        detail_container.mount(hint_bar)

    def _open_files_in_editor(self, result: ViewFilesResult) -> None:
        """Open files in $EDITOR (requires suspend)."""
        import subprocess

        def run_editor() -> None:
            editor = os.environ.get("EDITOR", "vi")
            editor_args = build_editor_args(editor, result.files)
            subprocess.run(editor_args, check=False)

        with self.suspend():  # type: ignore[attr-defined]
            run_editor()

    def _view_files_with_pager(self, files: list[str]) -> None:
        """View files using bat/cat with less (requires suspend)."""
        import shlex
        import shutil
        import subprocess

        def run_viewer() -> None:
            viewer = "bat" if shutil.which("bat") else "cat"
            quoted_files = " ".join(shlex.quote(f) for f in files)
            if viewer == "bat":
                cmd = f"bat --color=always {quoted_files} | less -R"
            else:
                cmd = f"cat {quoted_files} | less"
            subprocess.run(cmd, shell=True, check=False)

        with self.suspend():  # type: ignore[attr-defined]
            run_viewer()

    def _copy_files_to_clipboard(self, files: list[str]) -> None:
        """Copy file paths to system clipboard."""
        import subprocess
        import sys

        home = str(Path.home())
        shortened_files = [
            f.replace(home, "~", 1) if f.startswith(home) else f for f in files
        ]
        content = " ".join(shortened_files)

        if sys.platform == "darwin":
            clipboard_cmd = ["pbcopy"]
        elif sys.platform.startswith("linux"):
            clipboard_cmd = ["xclip", "-selection", "clipboard"]
        else:
            self.notify(  # type: ignore[attr-defined]
                f"Clipboard not supported on {sys.platform}", severity="error"
            )
            return

        try:
            subprocess.run(clipboard_cmd, input=content, text=True, check=True)
            self.notify(f"Copied {len(files)} path(s) to clipboard")  # type: ignore[attr-defined]
        except subprocess.CalledProcessError as e:
            self.notify(  # type: ignore[attr-defined]
                f"Clipboard command failed: {e}", severity="error"
            )
        except FileNotFoundError:
            self.notify(  # type: ignore[attr-defined]
                f"{clipboard_cmd[0]} not found", severity="error"
            )

"""Rename action methods for the ace TUI app."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...changespec import ChangeSpec


class RenameMixin:
    """Mixin providing rename CL action."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: str

    def action_rename_cl(self) -> None:
        """Show rename modal for the current ChangeSpec.

        Only available on the CLs tab for non-Submitted ChangeSpecs.
        """
        from ...changespec import get_base_status
        from ..modals import RenameCLModal

        if self.current_tab != "changespecs":
            return

        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Validate status - rename not available for Submitted or Reverted
        base_status = get_base_status(changespec.status)
        if base_status in ("Submitted", "Reverted"):
            self.notify(  # type: ignore[attr-defined]
                "Rename not available for Submitted/Reverted ChangeSpecs",
                severity="warning",
            )
            return

        def handle_rename_result(new_name: str | None) -> None:
            """Handle the rename modal result."""
            if new_name is None:
                return
            self._execute_rename(changespec, new_name)

        self.push_screen(  # type: ignore[attr-defined]
            RenameCLModal(
                current_name=changespec.name,
                project_file_path=changespec.file_path,
                status=base_status,
            ),
            handle_rename_result,
        )

    def _execute_rename(self, changespec: ChangeSpec, new_name: str) -> None:
        """Execute the rename operation.

        Args:
            changespec: The ChangeSpec to rename.
            new_name: The new name for the ChangeSpec.
        """
        from running_field import (
            claim_workspace,
            get_first_available_axe_workspace,
            get_workspace_directory_for_num,
            release_workspace,
            update_running_field_cl_name,
        )
        from status_state_machine import update_parent_references_atomic

        from ace.revert import update_changespec_name_atomic

        from ...changespec import get_base_status

        base_status = get_base_status(changespec.status)
        old_name = changespec.name
        project_basename = os.path.basename(changespec.file_path).replace(".gp", "")
        workspace_num: int | None = None

        def run_handler() -> tuple[bool, str]:
            """Execute rename in suspended TUI context.

            Returns:
                Tuple of (success, message)
            """
            nonlocal workspace_num

            # For Reverted CLs, skip Mercurial operations (no CL exists)
            if base_status == "Reverted":
                # Just update the spec file references
                try:
                    update_changespec_name_atomic(
                        changespec.file_path, old_name, new_name
                    )
                    update_parent_references_atomic(
                        changespec.file_path, old_name, new_name
                    )
                    update_running_field_cl_name(
                        changespec.file_path, old_name, new_name
                    )
                    return (True, f"Renamed {old_name} to {new_name}")
                except Exception as e:
                    return (False, f"Failed to update spec file: {e}")

            # Get workspace info
            workspace_num = get_first_available_axe_workspace(changespec.file_path)
            workflow_name = f"rename-{old_name}"

            try:
                workspace_dir, _ = get_workspace_directory_for_num(
                    workspace_num, project_basename
                )
            except RuntimeError as e:
                return (False, f"Failed to get workspace directory: {e}")

            # Claim workspace
            pid = os.getpid()
            if not claim_workspace(
                changespec.file_path, workspace_num, workflow_name, pid, old_name
            ):
                return (False, "Failed to claim workspace")

            try:
                # Checkout the CL
                print(f"Checking out {old_name}...")
                try:
                    result = subprocess.run(
                        ["bb_hg_update", old_name],
                        cwd=workspace_dir,
                        capture_output=False,
                        timeout=300,
                    )
                    if result.returncode != 0:
                        return (
                            False,
                            f"bb_hg_update failed with return code {result.returncode}",
                        )
                except subprocess.TimeoutExpired:
                    return (False, "bb_hg_update timed out")
                except FileNotFoundError:
                    return (False, "bb_hg_update command not found")

                # Rename the CL in Mercurial
                print(f"Renaming to {new_name}...")
                try:
                    result = subprocess.run(
                        ["bb_hg_rename", new_name],
                        cwd=workspace_dir,
                        capture_output=False,
                        timeout=300,
                    )
                    if result.returncode != 0:
                        return (
                            False,
                            f"bb_hg_rename failed with return code {result.returncode}",
                        )
                except subprocess.TimeoutExpired:
                    return (False, "bb_hg_rename timed out")
                except FileNotFoundError:
                    return (False, "bb_hg_rename command not found")

                # Update spec file references
                print("Updating spec file references...")
                try:
                    update_changespec_name_atomic(
                        changespec.file_path, old_name, new_name
                    )
                    update_parent_references_atomic(
                        changespec.file_path, old_name, new_name
                    )
                    update_running_field_cl_name(
                        changespec.file_path, old_name, new_name
                    )
                except Exception as e:
                    return (False, f"Failed to update spec file: {e}")

                return (True, f"Renamed {old_name} to {new_name}")

            finally:
                # Always release workspace
                if workspace_num is not None:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        workflow_name,
                        old_name,
                    )

        with self.suspend():  # type: ignore[attr-defined]
            success, message = run_handler()

        if success:
            self.notify(message)  # type: ignore[attr-defined]
        else:
            self.notify(f"Rename failed: {message}", severity="error")  # type: ignore[attr-defined]

        self._reload_and_reposition()  # type: ignore[attr-defined]

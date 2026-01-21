"""Sync action methods for the ace TUI app."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

from commit_utils import run_bb_hg_clean

if TYPE_CHECKING:
    from ...changespec import ChangeSpec


class SyncMixin:
    """Mixin providing workspace sync action."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int

    def action_sync(self) -> None:
        """Sync the current ChangeSpec's workspace.

        This action:
        1. Validates STATUS is not "Submitted" or "Reverted"
        2. Gets first available axe workspace (100-199 range)
        3. Claims workspace
        4. Runs `bb_hg_update {cl_name}` to checkout the CL
        5. Runs `bb_hg_sync` to sync the workspace
        6. Releases workspace in finally block
        7. Shows output via self.suspend() context manager
        8. Reports success/failure via self.notify()
        """
        from running_field import (
            claim_workspace,
            get_first_available_axe_workspace,
            get_workspace_directory_for_num,
            release_workspace,
        )

        from ...changespec import get_base_status

        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Validate status
        base_status = get_base_status(changespec.status)
        if base_status in ("Reverted", "Submitted"):
            self.notify(  # type: ignore[attr-defined]
                "Sync not available for Reverted/Submitted ChangeSpecs",
                severity="warning",
            )
            return

        project_basename = os.path.basename(changespec.file_path).replace(".gp", "")
        workspace_num: int | None = None

        def run_handler() -> tuple[bool, str]:
            """Execute sync in suspended TUI context.

            Returns:
                Tuple of (success, message)
            """
            nonlocal workspace_num

            # Get workspace info
            workspace_num = get_first_available_axe_workspace(changespec.file_path)
            workflow_name = f"sync-{changespec.name}"

            try:
                workspace_dir, _ = get_workspace_directory_for_num(
                    workspace_num, project_basename
                )
            except RuntimeError as e:
                return (False, f"Failed to get workspace directory: {e}")

            # Claim workspace (use our process ID since this is synchronous)
            pid = os.getpid()
            if not claim_workspace(
                changespec.file_path, workspace_num, workflow_name, pid, changespec.name
            ):
                return (False, "Failed to claim workspace")

            try:
                # Clean workspace before switching branches
                clean_success, clean_error = run_bb_hg_clean(
                    workspace_dir, f"{changespec.name}-sync"
                )
                if not clean_success:
                    print(f"Warning: bb_hg_clean failed: {clean_error}")

                # Checkout the CL
                print(f"Checking out {changespec.name}...")
                try:
                    result = subprocess.run(
                        ["bb_hg_update", changespec.name],
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

                # Run bb_hg_sync
                print("Syncing workspace...")
                try:
                    result = subprocess.run(
                        ["bb_hg_sync"],
                        cwd=workspace_dir,
                        capture_output=False,
                        timeout=600,  # 10 minutes for sync
                    )
                    if result.returncode != 0:
                        return (
                            False,
                            f"bb_hg_sync failed with return code {result.returncode}",
                        )
                except subprocess.TimeoutExpired:
                    return (False, "bb_hg_sync timed out")
                except FileNotFoundError:
                    return (False, "bb_hg_sync command not found")

                return (True, f"Synced {changespec.name}")

            finally:
                # Always release workspace
                if workspace_num is not None:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        workflow_name,
                        changespec.name,
                    )

        with self.suspend():  # type: ignore[attr-defined]
            success, message = run_handler()

        if success:
            self.notify(message)  # type: ignore[attr-defined]
        else:
            self.notify(f"Sync failed: {message}", severity="error")  # type: ignore[attr-defined]

        self._reload_and_reposition()  # type: ignore[attr-defined]

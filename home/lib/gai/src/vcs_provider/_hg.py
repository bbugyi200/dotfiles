"""Mercurial VCS provider implementation."""

import os
import subprocess

from ._base import VCSProvider
from ._registry import register_provider
from ._types import CommandOutput


class _HgProvider(VCSProvider):
    """VCS provider backed by Mercurial and Google-internal ``bb_hg_*`` helpers."""

    # --- Private helpers ---

    def _run(
        self,
        cmd: list[str],
        cwd: str,
        *,
        timeout: int = 300,
        capture_output: bool = True,
    ) -> CommandOutput:
        """Run a subprocess command and return a :class:`CommandOutput`."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=capture_output,
                text=True,
                check=False,
                timeout=timeout,
            )
            return CommandOutput(result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return CommandOutput(1, "", f"{cmd[0]} timed out")
        except FileNotFoundError:
            return CommandOutput(1, "", f"{cmd[0]} command not found")
        except Exception as e:
            return CommandOutput(1, "", f"Error running {cmd[0]}: {e}")

    def _run_shell(self, cmd: str, cwd: str, *, timeout: int = 300) -> CommandOutput:
        """Run a shell command string and return a :class:`CommandOutput`."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            return CommandOutput(result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return CommandOutput(1, "", "Command timed out")
        except Exception as e:
            return CommandOutput(1, "", f"Error: {e}")

    def _to_result(self, out: CommandOutput, op_name: str) -> tuple[bool, str | None]:
        """Convert a :class:`CommandOutput` to ``(success, error_or_none)``."""
        if out.success:
            return (True, None)
        error_msg = out.stderr.strip() or out.stdout.strip()
        return (
            False,
            f"{op_name} failed: {error_msg}" if error_msg else f"{op_name} failed",
        )

    # --- Core abstract methods ---

    def checkout(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_update", revision], cwd)
        return self._to_result(out, "bb_hg_update")

    def diff(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["hg", "diff"], cwd)
        if not out.success:
            return (False, f"hg diff failed: {out.stderr.strip()}")
        text = out.stdout.strip()
        return (True, text if text else None)

    def diff_revision(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["hg", "diff", "-c", revision], cwd)
        if not out.success:
            return (False, f"hg diff failed: {out.stderr.strip()}")
        return (True, out.stdout)

    def apply_patch(self, patch_path: str, cwd: str) -> tuple[bool, str | None]:
        expanded = os.path.expanduser(patch_path)
        if not os.path.exists(expanded):
            return (False, f"Diff file not found: {patch_path}")
        out = self._run(["hg", "import", "--no-commit", expanded], cwd)
        if not out.success:
            return (False, out.stderr.strip() or "hg import failed")
        return (True, None)

    def apply_patches(
        self, patch_paths: list[str], cwd: str
    ) -> tuple[bool, str | None]:
        if not patch_paths:
            return (True, None)
        expanded: list[str] = []
        for p in patch_paths:
            ep = os.path.expanduser(p)
            if not os.path.exists(ep):
                return (False, f"Diff file not found: {p}")
            expanded.append(ep)
        out = self._run(["hg", "import", "--no-commit"] + expanded, cwd)
        if not out.success:
            return (False, out.stderr.strip() or "hg import failed")
        return (True, None)

    def add_remove(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["hg", "addremove"], cwd)
        return self._to_result(out, "hg addremove")

    def clean_workspace(self, cwd: str) -> tuple[bool, str | None]:
        # Revert tracked changes
        out = self._run(["hg", "update", "--clean", "."], cwd)
        if not out.success:
            return (False, f"hg update --clean failed: {out.stderr.strip()}")
        # Remove untracked files
        out = self._run(["hg", "clean"], cwd)
        if not out.success:
            return (False, f"hg clean failed: {out.stderr.strip()}")
        return (True, None)

    def commit(self, name: str, logfile: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run_shell(f'hg commit --name "{name}" --logfile "{logfile}"', cwd)
        return self._to_result(out, "hg commit")

    def amend(
        self, note: str, cwd: str, *, no_upload: bool = False
    ) -> tuple[bool, str | None]:
        cmd = ["bb_hg_amend"]
        if no_upload:
            cmd.append("--no-upload")
        cmd.append(note)
        out = self._run(cmd, cwd)
        return self._to_result(out, "bb_hg_amend")

    def rename_branch(self, new_name: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_rename", new_name], cwd)
        return self._to_result(out, "bb_hg_rename")

    def rebase(
        self, branch_name: str, new_parent: str, cwd: str
    ) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_rebase", branch_name, new_parent], cwd, timeout=600)
        return self._to_result(out, "bb_hg_rebase")

    def archive(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_archive", revision], cwd)
        return self._to_result(out, "bb_hg_archive")

    def prune(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_prune", revision], cwd)
        return self._to_result(out, "bb_hg_prune")

    def stash_and_clean(
        self, diff_name: str, cwd: str, *, timeout: int = 300
    ) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_clean", diff_name], cwd, timeout=timeout)
        if not out.success:
            error_msg = out.stderr.strip() or out.stdout.strip() or "no error output"
            return (False, error_msg)
        return (True, None)

    # --- Optional core methods ---

    def get_default_parent_revision(self, cwd: str) -> str:
        return "p4head"

    def sync_workspace(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_sync"], cwd, timeout=600)
        return self._to_result(out, "bb_hg_sync")

    # --- VCS-agnostic method overrides ---

    def prepare_description_for_reword(self, description: str) -> str:
        """Escape a description for bb_hg_reword's ``$'...'`` quoting.

        bb_hg_reword uses ``bash -c "hg reword -m $'$1'"`` which interprets
        ANSI-C escape sequences. Python passes actual newline chars, but the
        script needs literal ``\\n`` sequences that ``$'...'`` converts back.
        """
        return (
            description.replace("\\", "\\\\")  # backslashes first
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace("\r", "\\r")
        )

    def get_change_url(self, cwd: str) -> tuple[bool, str | None]:
        success, number = self.get_cl_number(cwd)
        if not success:
            return (False, None)
        if number:
            return (True, f"http://cl/{number}")
        return (True, None)

    # --- Google-internal methods ---

    def reword(self, description: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_reword", description], cwd)
        return self._to_result(out, "bb_hg_reword")

    def reword_add_tag(
        self, tag_name: str, tag_value: str, cwd: str
    ) -> tuple[bool, str | None]:
        out = self._run(["bb_hg_reword", "--add-tag", tag_name, tag_value], cwd)
        return self._to_result(out, "bb_hg_reword")

    def get_description(
        self, revision: str, cwd: str, *, short: bool = False
    ) -> tuple[bool, str | None]:
        cmd = ["cl_desc"]
        if short:
            cmd.append("-s")
        else:
            cmd.extend(["-r", revision])
        out = self._run(cmd, cwd)
        if not out.success:
            return (False, out.stderr.strip() or "cl_desc failed")
        return (True, out.stdout)

    def get_branch_name(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run_shell("branch_name", cwd)
        if not out.success:
            return (False, "branch_name command failed")
        name = out.stdout.strip()
        return (True, name) if name else (True, None)

    def get_cl_number(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run_shell("branch_number", cwd)
        if not out.success:
            return (False, "branch_number command failed")
        number = out.stdout.strip()
        if number and number.isdigit():
            return (True, number)
        return (True, None)

    def get_workspace_name(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run_shell("workspace_name", cwd)
        if not out.success:
            return (False, "workspace_name command failed")
        name = out.stdout.strip()
        return (True, name) if name else (True, None)

    def has_local_changes(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run_shell("branch_local_changes", cwd)
        # branch_local_changes outputs text if there are changes, empty if not
        text = out.stdout.strip()
        return (True, text if text else None)

    def get_bug_number(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run_shell("branch_bug", cwd)
        if not out.success:
            return (False, "branch_bug command failed")
        return (True, out.stdout.strip())

    def mail(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        # Mail is run non-interactively (capture_output=False in original)
        # but we capture to check success
        out = self._run(["hg", "mail", "-r", revision], cwd)
        return self._to_result(out, "hg mail")

    def fix(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run_shell("hg fix", cwd)
        return self._to_result(out, "hg fix")

    def upload(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run_shell("hg upload tree", cwd)
        return self._to_result(out, "hg upload tree")

    def find_reviewers(self, cl_number: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["p4", "findreviewers", "-c", cl_number], cwd)
        if not out.success:
            return (False, out.stderr.strip() or "p4 findreviewers failed")
        return (True, out.stdout)

    def rewind(self, diff_paths: list[str], cwd: str) -> tuple[bool, str | None]:
        out = self._run(["gai_rewind"] + diff_paths, cwd, timeout=600)
        return self._to_result(out, "gai_rewind")


# Self-register when imported
register_provider("hg", _HgProvider)

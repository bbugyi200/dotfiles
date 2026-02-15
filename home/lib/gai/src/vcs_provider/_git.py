"""Git VCS provider implementation."""

import os
import subprocess

from ._base import VCSProvider
from ._registry import register_provider
from ._types import CommandOutput


class _GitProvider(VCSProvider):
    """VCS provider backed by git."""

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
        out = self._run(["git", "checkout", revision], cwd)
        return self._to_result(out, "git checkout")

    def diff(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "diff", "HEAD"], cwd)
        if not out.success:
            # Fallback for empty repos (no HEAD yet)
            out = self._run(["git", "diff"], cwd)
            if not out.success:
                return (False, f"git diff failed: {out.stderr.strip()}")
        text = out.stdout.strip()
        return (True, text if text else None)

    def diff_revision(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "diff", f"{revision}~1", revision], cwd)
        if not out.success:
            # Fallback for root commits (no parent)
            out = self._run(["git", "show", "--format=", "--patch", revision], cwd)
            if not out.success:
                return (False, f"git diff failed: {out.stderr.strip()}")
        return (True, out.stdout)

    def apply_patch(self, patch_path: str, cwd: str) -> tuple[bool, str | None]:
        expanded = os.path.expanduser(patch_path)
        if not os.path.exists(expanded):
            return (False, f"Diff file not found: {patch_path}")
        out = self._run(["git", "apply", expanded], cwd)
        if not out.success:
            return (False, out.stderr.strip() or "git apply failed")
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
        out = self._run(["git", "apply"] + expanded, cwd)
        if not out.success:
            return (False, out.stderr.strip() or "git apply failed")
        return (True, None)

    def add_remove(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "add", "-A"], cwd)
        return self._to_result(out, "git add -A")

    def clean_workspace(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "reset", "--hard", "HEAD"], cwd)
        if not out.success:
            return (False, f"git reset --hard failed: {out.stderr.strip()}")
        out = self._run(["git", "clean", "-fd"], cwd)
        if not out.success:
            return (False, f"git clean -fd failed: {out.stderr.strip()}")
        return (True, None)

    def commit(self, name: str, logfile: str, cwd: str) -> tuple[bool, str | None]:
        # Check current branch; create new branch if not already on `name`
        branch_out = self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
        current_branch = branch_out.stdout.strip() if branch_out.success else ""
        if current_branch != name:
            checkout_out = self._run(["git", "checkout", "-b", name], cwd)
            if not checkout_out.success:
                return self._to_result(checkout_out, "git checkout -b")
        out = self._run(["git", "commit", "-F", logfile], cwd)
        return self._to_result(out, "git commit")

    def amend(
        self, note: str, cwd: str, *, no_upload: bool = False
    ) -> tuple[bool, str | None]:
        # no_upload flag silently ignored (Google-internal)
        out = self._run(["git", "commit", "--amend", "-m", note], cwd)
        return self._to_result(out, "git commit --amend")

    def rename_branch(self, new_name: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "branch", "-m", new_name], cwd)
        return self._to_result(out, "git branch -m")

    def rebase(
        self, branch_name: str, new_parent: str, cwd: str
    ) -> tuple[bool, str | None]:
        out = self._run(
            ["git", "rebase", "--onto", new_parent, branch_name], cwd, timeout=600
        )
        return self._to_result(out, "git rebase")

    def archive(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        # Tag preserves commits, branch delete hides them
        tag_out = self._run(["git", "tag", f"archive/{revision}", revision], cwd)
        if not tag_out.success:
            return self._to_result(tag_out, "git tag")
        delete_out = self._run(["git", "branch", "-D", revision], cwd)
        if not delete_out.success:
            return self._to_result(delete_out, "git branch -D")
        return (True, None)

    def prune(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "branch", "-D", revision], cwd)
        return self._to_result(out, "git branch -D")

    def stash_and_clean(
        self, diff_name: str, cwd: str, *, timeout: int = 300
    ) -> tuple[bool, str | None]:
        # Save current diff to file, then clean workspace
        diff_out = self._run(["git", "diff", "HEAD"], cwd, timeout=timeout)
        if not diff_out.success:
            error_msg = (
                diff_out.stderr.strip() or diff_out.stdout.strip() or "no error output"
            )
            return (False, error_msg)
        try:
            with open(diff_name, "w") as f:
                f.write(diff_out.stdout)
        except OSError as e:
            return (False, f"Failed to write diff file: {e}")
        # Clean workspace
        reset_out = self._run(["git", "reset", "--hard", "HEAD"], cwd, timeout=timeout)
        if not reset_out.success:
            return (False, f"git reset --hard failed: {reset_out.stderr.strip()}")
        clean_out = self._run(["git", "clean", "-fd"], cwd, timeout=timeout)
        if not clean_out.success:
            return (False, f"git clean -fd failed: {clean_out.stderr.strip()}")
        return (True, None)

    # --- Optional core methods ---

    def get_default_parent_revision(self, cwd: str) -> str:
        # Reuse logic from sync_workspace for detecting default branch
        branch_out = self._run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"], cwd)
        default_branch = "main"
        if branch_out.success:
            ref = branch_out.stdout.strip()
            if ref:
                default_branch = ref.rsplit("/", 1)[-1]
        return f"origin/{default_branch}"

    def sync_workspace(self, cwd: str) -> tuple[bool, str | None]:
        # Fetch latest from origin
        fetch_out = self._run(["git", "fetch", "origin"], cwd, timeout=600)
        if not fetch_out.success:
            return self._to_result(fetch_out, "git fetch origin")
        # Determine default branch (main or master)
        branch_out = self._run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"], cwd)
        default_branch = "main"
        if branch_out.success:
            # Output like "refs/remotes/origin/main"
            ref = branch_out.stdout.strip()
            if ref:
                default_branch = ref.rsplit("/", 1)[-1]
        # Rebase onto the default branch
        rebase_out = self._run(
            ["git", "rebase", f"origin/{default_branch}"], cwd, timeout=600
        )
        return self._to_result(rebase_out, "git rebase")

    # --- VCS-agnostic method overrides ---

    def get_change_url(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["gh", "pr", "view", "--json", "url", "-q", ".url"], cwd)
        if out.success:
            url = out.stdout.strip()
            return (True, url) if url else (True, None)
        # No PR exists yet (gh exits non-zero)
        return (True, None)

    def get_cl_number(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["gh", "pr", "view", "--json", "number", "-q", ".number"], cwd)
        if out.success:
            number = out.stdout.strip()
            return (True, number) if number else (True, None)
        # No PR exists yet
        return (True, None)

    def get_bug_number(self, cwd: str) -> tuple[bool, str | None]:
        return (True, "")

    def fix(self, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def upload(self, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def mail(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        # Push to remote
        out = self._run(["git", "push", "-u", "origin", revision], cwd)
        if not out.success:
            return self._to_result(out, "git push")
        # Check if PR already exists
        pr_check = self._run(
            ["gh", "pr", "view", "--json", "number", "-q", ".number"], cwd
        )
        if not pr_check.success:
            # No PR yet — create one
            pr_create = self._run(["gh", "pr", "create", "--fill"], cwd)
            if not pr_create.success:
                return self._to_result(pr_create, "gh pr create")
        return (True, None)

    def reword_add_tag(
        self, tag_name: str, tag_value: str, cwd: str
    ) -> tuple[bool, str | None]:
        # Read current commit message
        out = self._run(["git", "log", "--format=%B", "-n1", "HEAD"], cwd)
        if not out.success:
            return (False, out.stderr.strip() or "git log failed")
        current_msg = out.stdout.rstrip("\n")
        new_msg = f"{current_msg}\n{tag_name}={tag_value}"
        amend_out = self._run(["git", "commit", "--amend", "-m", new_msg], cwd)
        return self._to_result(amend_out, "git commit --amend")

    # --- Optional methods with git equivalents ---

    def get_branch_name(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
        if not out.success:
            return (False, "git rev-parse --abbrev-ref HEAD failed")
        name = out.stdout.strip()
        # Detached HEAD returns "HEAD"
        if not name or name == "HEAD":
            return (True, None)
        return (True, name)

    def get_description(
        self, revision: str, cwd: str, *, short: bool = False
    ) -> tuple[bool, str | None]:
        fmt = "%s" if short else "%B"
        out = self._run(["git", "log", f"--format={fmt}", "-n1", revision], cwd)
        if not out.success:
            return (False, out.stderr.strip() or "git log failed")
        return (True, out.stdout)

    def has_local_changes(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "status", "--porcelain"], cwd)
        if not out.success:
            return (False, out.stderr.strip() or "git status failed")
        text = out.stdout.strip()
        return (True, text if text else None)

    def get_workspace_name(self, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "config", "--get", "remote.origin.url"], cwd)
        if out.success and out.stdout.strip():
            url = out.stdout.strip()
            # Extract repo name from URL (handles .git suffix)
            name = os.path.basename(url)
            if name.endswith(".git"):
                name = name[:-4]
            return (True, name) if name else (True, None)
        # Fallback to repo root basename
        root_out = self._run(["git", "rev-parse", "--show-toplevel"], cwd)
        if root_out.success and root_out.stdout.strip():
            name = os.path.basename(root_out.stdout.strip())
            return (True, name) if name else (True, None)
        return (False, "Could not determine workspace name")

    def reword(self, description: str, cwd: str) -> tuple[bool, str | None]:
        out = self._run(["git", "commit", "--amend", "-m", description], cwd)
        return self._to_result(out, "git commit --amend")


# Self-register when imported
register_provider("git", _GitProvider)

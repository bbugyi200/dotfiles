"""Abstract base class defining the VCS provider interface."""

from abc import ABC, abstractmethod


class VCSProvider(ABC):
    """Abstract interface for version control system operations.

    All methods take an explicit ``cwd`` parameter and return
    ``tuple[bool, str | None]`` — ``(success, error_message)`` — matching
    the convention established by ``run_workspace_command()`` in
    ``gai_utils.py``.
    """

    # --- Core abstract methods (must be implemented by all providers) ---

    @abstractmethod
    def checkout(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        """Check out a revision / bookmark / branch."""

    @abstractmethod
    def diff(self, cwd: str) -> tuple[bool, str | None]:
        """Return the current uncommitted diff text.

        Returns ``(True, diff_text)`` when there are changes, or
        ``(True, None)`` when the working directory is clean.
        """

    @abstractmethod
    def diff_revision(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        """Return the diff for a specific revision.

        Returns ``(True, diff_text)`` on success.
        """

    @abstractmethod
    def apply_patch(self, patch_path: str, cwd: str) -> tuple[bool, str | None]:
        """Apply a single patch file without committing."""

    @abstractmethod
    def apply_patches(
        self, patch_paths: list[str], cwd: str
    ) -> tuple[bool, str | None]:
        """Apply multiple patch files without committing."""

    @abstractmethod
    def add_remove(self, cwd: str) -> tuple[bool, str | None]:
        """Stage new and deleted files (``hg addremove`` / ``git add -A``)."""

    @abstractmethod
    def clean_workspace(self, cwd: str) -> tuple[bool, str | None]:
        """Revert all tracked changes and remove untracked files."""

    @abstractmethod
    def commit(self, name: str, logfile: str, cwd: str) -> tuple[bool, str | None]:
        """Create a new commit."""

    @abstractmethod
    def amend(
        self, note: str, cwd: str, *, no_upload: bool = False
    ) -> tuple[bool, str | None]:
        """Amend the current commit."""

    @abstractmethod
    def rename_branch(self, new_name: str, cwd: str) -> tuple[bool, str | None]:
        """Rename the current bookmark / branch."""

    @abstractmethod
    def rebase(
        self, branch_name: str, new_parent: str, cwd: str
    ) -> tuple[bool, str | None]:
        """Rebase a branch onto a new parent."""

    @abstractmethod
    def archive(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        """Archive (hide) a revision."""

    @abstractmethod
    def prune(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        """Permanently delete a revision."""

    @abstractmethod
    def stash_and_clean(
        self, diff_name: str, cwd: str, *, timeout: int = 300
    ) -> tuple[bool, str | None]:
        """Save uncommitted changes to a diff file and clean the workspace."""

    # --- Google-internal methods (default raises NotImplementedError) ---

    def reword(self, description: str, cwd: str) -> tuple[bool, str | None]:
        """Reword the current commit's description."""
        raise NotImplementedError("reword is not supported by this VCS provider")

    def reword_add_tag(
        self, tag_name: str, tag_value: str, cwd: str
    ) -> tuple[bool, str | None]:
        """Add a tag to the current commit's description."""
        raise NotImplementedError(
            "reword_add_tag is not supported by this VCS provider"
        )

    def get_description(
        self, revision: str, cwd: str, *, short: bool = False
    ) -> tuple[bool, str | None]:
        """Get the commit description for a revision."""
        raise NotImplementedError(
            "get_description is not supported by this VCS provider"
        )

    def get_branch_name(self, cwd: str) -> tuple[bool, str | None]:
        """Get the current branch / bookmark name."""
        raise NotImplementedError(
            "get_branch_name is not supported by this VCS provider"
        )

    def get_cl_number(self, cwd: str) -> tuple[bool, str | None]:
        """Get the CL / change number for the current branch."""
        raise NotImplementedError("get_cl_number is not supported by this VCS provider")

    def get_workspace_name(self, cwd: str) -> tuple[bool, str | None]:
        """Get the workspace / repository name."""
        raise NotImplementedError(
            "get_workspace_name is not supported by this VCS provider"
        )

    def has_local_changes(self, cwd: str) -> tuple[bool, str | None]:
        """Check whether the working directory has uncommitted changes.

        Returns ``(True, "true"/"false")`` on success.
        """
        raise NotImplementedError(
            "has_local_changes is not supported by this VCS provider"
        )

    def get_bug_number(self, cwd: str) -> tuple[bool, str | None]:
        """Get the bug number associated with the current branch."""
        raise NotImplementedError(
            "get_bug_number is not supported by this VCS provider"
        )

    def mail(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        """Mail / upload a CL for review."""
        raise NotImplementedError("mail is not supported by this VCS provider")

    def fix(self, cwd: str) -> tuple[bool, str | None]:
        """Run automatic code fixes (``hg fix``)."""
        raise NotImplementedError("fix is not supported by this VCS provider")

    def upload(self, cwd: str) -> tuple[bool, str | None]:
        """Upload the current change for review."""
        raise NotImplementedError("upload is not supported by this VCS provider")

    def find_reviewers(self, cl_number: str, cwd: str) -> tuple[bool, str | None]:
        """Find suggested reviewers for a CL."""
        raise NotImplementedError(
            "find_reviewers is not supported by this VCS provider"
        )

    def rewind(self, diff_paths: list[str], cwd: str) -> tuple[bool, str | None]:
        """Rewind changes by importing diffs in reverse."""
        raise NotImplementedError("rewind is not supported by this VCS provider")

    # --- VCS-agnostic methods (default implementations) ---

    def prepare_description_for_reword(self, description: str) -> str:
        """Prepare a description string for the provider's reword command.

        The default implementation returns the description unchanged.
        Providers that need escaping (e.g. hg's ``$'...'`` quoting) should
        override this method.
        """
        return description

    def get_change_url(self, cwd: str) -> tuple[bool, str | None]:
        """Get the URL for the current change (CL URL or PR URL).

        Returns ``(True, url)`` on success, ``(True, None)`` if no change
        exists yet (e.g. git branch with no PR).
        """
        raise NotImplementedError(
            "get_change_url is not supported by this VCS provider"
        )

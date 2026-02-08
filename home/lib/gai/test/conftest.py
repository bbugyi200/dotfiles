"""Pytest configuration for gai tests."""

import sys
import tempfile
from pathlib import Path

# Add src and test directories to path so we can import modules
# NOTE: This must happen BEFORE importing any gai modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from ace.changespec import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
)


@pytest.fixture
def make_changespec() -> "type[_ChangeSpecFactory]":  # Return a callable factory class
    """Fixture that provides a factory for creating ChangeSpec objects for testing."""
    return _ChangeSpecFactory


class _ChangeSpecFactory:
    """Factory class for creating ChangeSpec objects in tests."""

    @staticmethod
    def create(
        name: str = "test",
        description: str = "desc",
        status: str = "Drafted",
        cl: str | None = None,
        parent: str | None = None,
        file_path: str = "/home/user/.gai/projects/myproject/myproject.gp",
        commits: list[CommitEntry] | None = None,
        hooks: list[HookEntry] | None = None,
        comments: list[CommentEntry] | None = None,
    ) -> ChangeSpec:
        """Create a ChangeSpec for testing."""
        return ChangeSpec(
            name=name,
            description=description,
            parent=parent,
            cl=cl,
            status=status,
            test_targets=None,
            kickstart=None,
            file_path=file_path,
            line_number=1,
            commits=commits,
            hooks=hooks,
            comments=comments,
        )

    @staticmethod
    def create_with_file(
        name: str = "test_feature",
        cl: str | None = "http://cl/123456789",
        status: str = "Mailed",
        parent: str | None = None,
    ) -> ChangeSpec:
        """Create a ChangeSpec backed by a temporary .gp file on disk.

        The caller is responsible for cleaning up the temp file via
        ``Path(cs.file_path).unlink()``.
        """
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
            parent_val = parent if parent else "None"
            cl_val = cl if cl else "None"
            f.write(f"""# Test Project

## ChangeSpec

NAME: {name}
DESCRIPTION:
  A test feature
PARENT: {parent_val}
CL: {cl_val}
STATUS: {status}

---
""")
            return ChangeSpec(
                name=name,
                description="A test feature",
                parent=parent,
                cl=cl,
                status=status,
                test_targets=None,
                kickstart=None,
                file_path=f.name,
                line_number=6,
            )

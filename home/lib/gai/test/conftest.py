"""Pytest configuration for gai tests."""

import sys
from pathlib import Path

import pytest
from ace.changespec import (
    ChangeSpec,
    CommentEntry,
    HistoryEntry,
    HookEntry,
)

# Add parent directory to path so we can import gai modules
sys.path.insert(0, str(Path(__file__).parent.parent))


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
        file_path: str = "/home/user/.gai/projects/myproject/myproject.gp",
        history: list[HistoryEntry] | None = None,
        hooks: list[HookEntry] | None = None,
        comments: list[CommentEntry] | None = None,
    ) -> ChangeSpec:
        """Create a ChangeSpec for testing."""
        return ChangeSpec(
            name=name,
            description=description,
            parent=None,
            cl=None,
            status=status,
            test_targets=None,
            kickstart=None,
            file_path=file_path,
            line_number=1,
            history=history,
            hooks=hooks,
            comments=comments,
        )

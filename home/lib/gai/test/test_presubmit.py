"""Tests for work.presubmit module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from work.changespec import ChangeSpec
from work.operations import get_available_workflows
from work.presubmit import (
    _get_presubmit_path,
    _get_workspace_directory,
    _update_changespec_presubmit_field,
)


def _create_test_changespec(
    name: str = "test_feature",
    status: str = "Drafted",
    file_path: str = "/tmp/testproject.gp",
) -> ChangeSpec:
    """Create a test ChangeSpec."""
    return ChangeSpec(
        name=name,
        description="Test feature",
        parent=None,
        cl="123456",
        status=status,
        test_targets=None,
        kickstart=None,
        file_path=file_path,
        line_number=1,
    )


def test_get_available_workflows_failing_tests() -> None:
    """Test that Failing Tests status returns fix-tests workflow."""
    cs = _create_test_changespec(status="Failing Tests")
    workflows = get_available_workflows(cs)
    assert workflows == ["fix-tests"]


def test_get_available_workflows_drafted_no_workflows() -> None:
    """Test that Drafted status returns no workflows."""
    cs = _create_test_changespec(status="Drafted")
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_workspace_directory_with_env_vars() -> None:
    """Test _get_workspace_directory when env vars are set."""
    cs = _create_test_changespec(
        file_path="/home/user/.gai/projects/myproject/myproject.gp"
    )

    with patch.dict(
        "os.environ",
        {"GOOG_CLOUD_DIR": "/google/cloud", "GOOG_SRC_DIR_BASE": "src/google3"},
    ):
        result = _get_workspace_directory(cs)

    assert result == "/google/cloud/myproject/src/google3"


def test_get_workspace_directory_missing_cloud_dir() -> None:
    """Test _get_workspace_directory when GOOG_CLOUD_DIR is not set."""
    cs = _create_test_changespec()

    with patch.dict(
        "os.environ",
        {"GOOG_SRC_DIR_BASE": "src/google3"},
        clear=True,
    ):
        result = _get_workspace_directory(cs)

    assert result is None


def test_get_workspace_directory_missing_src_dir_base() -> None:
    """Test _get_workspace_directory when GOOG_SRC_DIR_BASE is not set."""
    cs = _create_test_changespec()

    with patch.dict(
        "os.environ",
        {"GOOG_CLOUD_DIR": "/google/cloud"},
        clear=True,
    ):
        result = _get_workspace_directory(cs)

    assert result is None


def test_get_presubmit_path_format() -> None:
    """Test that _get_presubmit_path generates correct format."""
    cs = _create_test_changespec(
        name="my/test_feature",
        file_path="/home/user/.gai/projects/testproj/testproj.gp",
    )

    with patch("work.presubmit.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "20250101_120000"
        result = _get_presubmit_path(cs)

    # Check that the path contains expected components
    assert "testproj" in result
    assert "presubmit_output" in result
    assert "my_test_feature" in result  # Slashes and spaces replaced with _
    assert "20250101_120000" in result
    assert result.endswith(".log")


def test_update_changespec_presubmit_field_new_field() -> None:
    """Test adding new presubmit field to a ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

## ChangeSpec

NAME: Test Feature
DESCRIPTION:
  A test feature
PARENT: None
CL: 123456
STATUS: Drafted


---
"""
        )
        project_file = f.name

    try:
        result = _update_changespec_presubmit_field(
            project_file,
            "Test Feature",
            "/path/to/output.log",
        )

        assert result is True

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()

        assert "PRESUBMIT: /path/to/output.log" in content

    finally:
        Path(project_file).unlink()


def test_update_changespec_presubmit_field_existing_field() -> None:
    """Test updating existing presubmit field in a ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

## ChangeSpec

NAME: Test Feature
DESCRIPTION:
  A test feature
PARENT: None
CL: 123456
STATUS: Drafted
PRESUBMIT: /old/path/output.log


---
"""
        )
        project_file = f.name

    try:
        result = _update_changespec_presubmit_field(
            project_file,
            "Test Feature",
            "/new/path/output.log",
        )

        assert result is True

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()

        assert "PRESUBMIT: /new/path/output.log" in content
        # Old value should not be present
        assert "/old/path/output.log" not in content

    finally:
        Path(project_file).unlink()


def test_update_changespec_presubmit_field_multiple_changespecs() -> None:
    """Test that only the target ChangeSpec is updated."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

## ChangeSpec 1

NAME: Feature A
DESCRIPTION:
  First feature
PARENT: None
CL: 111111
STATUS: Drafted


## ChangeSpec 2

NAME: Feature B
DESCRIPTION:
  Second feature
PARENT: None
CL: 222222
STATUS: Mailed


---
"""
        )
        project_file = f.name

    try:
        result = _update_changespec_presubmit_field(
            project_file,
            "Feature A",
            "/path/to/output_a.log",
        )

        assert result is True

        # Verify only Feature A was updated
        with open(project_file) as f:
            content = f.read()

        # Feature A should have presubmit field
        assert "PRESUBMIT: /path/to/output_a.log" in content

        # The content around Feature B should not have presubmit field
        # (Feature B section should be unchanged)
        lines = content.split("\n")
        in_feature_b = False
        feature_b_has_presubmit = False

        for line in lines:
            if "NAME: Feature B" in line:
                in_feature_b = True
            elif "NAME:" in line:
                in_feature_b = False
            elif in_feature_b and "PRESUBMIT" in line:
                feature_b_has_presubmit = True

        assert not feature_b_has_presubmit

    finally:
        Path(project_file).unlink()


def test_update_changespec_presubmit_field_nonexistent_file() -> None:
    """Test handling of nonexistent project file."""
    result = _update_changespec_presubmit_field(
        "/nonexistent/path/file.md",
        "Test Feature",
        "/path/to/output.log",
    )

    assert result is False


def test_update_changespec_presubmit_field_at_end_of_file() -> None:
    """Test adding presubmit field when ChangeSpec is at end of file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

NAME: Test Feature
DESCRIPTION:
  A test feature
PARENT: None
CL: 123456
STATUS: Drafted
"""
        )
        project_file = f.name

    try:
        result = _update_changespec_presubmit_field(
            project_file,
            "Test Feature",
            "/path/to/output.log",
        )

        assert result is True

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()

        assert "PRESUBMIT: /path/to/output.log" in content

    finally:
        Path(project_file).unlink()

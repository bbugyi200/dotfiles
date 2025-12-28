"""Tests for the split_workflow module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from search.changespec import ChangeSpec
from search.split_workflow import SplitWorkflow
from search.split_workflow.agent import _extract_yaml_from_response
from search.split_workflow.spec import archive_spec_file
from search.split_workflow.utils import (
    generate_timestamp,
    get_editor,
    get_splits_directory,
    has_children,
)


def _create_test_changespec(
    name: str = "test_feature",
    parent: str | None = None,
    status: str = "Drafted",
) -> ChangeSpec:
    """Create a test ChangeSpec."""
    return ChangeSpec(
        name=name,
        description="Test description",
        parent=parent,
        cl=None,
        status=status,
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
    )


def test_generate_timestamp() -> None:
    """Test generate_timestamp returns valid format."""
    timestamp = generate_timestamp()

    # Should be 13 characters: YYmmdd_HHMMSS
    assert len(timestamp) == 13
    # Should have underscore at position 6
    assert timestamp[6] == "_"
    # Date and time parts should be digits
    assert timestamp[:6].isdigit()
    assert timestamp[7:].isdigit()


def test_get_splits_directory() -> None:
    """Test get_splits_directory returns expected path."""
    splits_dir = get_splits_directory()

    assert splits_dir.endswith(".gai/splits")
    assert splits_dir.startswith(str(Path.home()))


def test_archive_spec_file() -> None:
    """Test archive_spec_file saves spec and returns path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "search.split_workflow.spec.get_splits_directory", return_value=tmpdir
        ):
            spec_content = "- name: test\n  description: Test\n  files:\n    - a.py"
            archive_path = archive_spec_file("myfeature", spec_content, "251221_123456")

            # Check the file was created
            expected_path = os.path.join(tmpdir, "myfeature-251221_123456.yml")
            assert os.path.exists(expected_path)

            # Check content was written
            with open(expected_path) as f:
                assert f.read() == spec_content

            # Check returned path contains ~
            assert "~" in archive_path or tmpdir in archive_path


def test_has_children_with_no_children() -> None:
    """Test has_children returns False when no children exist."""
    parent = _create_test_changespec(name="parent_cl")
    unrelated = _create_test_changespec(name="other_cl")

    with patch(
        "search.split_workflow.utils.find_all_changespecs",
        return_value=[parent, unrelated],
    ):
        assert has_children("parent_cl") is False


def test_has_children_with_children() -> None:
    """Test has_children returns True when children exist."""
    parent = _create_test_changespec(name="parent_cl")
    child = _create_test_changespec(name="child_cl", parent="parent_cl")

    with patch(
        "search.split_workflow.utils.find_all_changespecs", return_value=[parent, child]
    ):
        assert has_children("parent_cl") is True


def test_has_children_ignores_reverted_children() -> None:
    """Test has_children returns False when only child is Reverted."""
    parent = _create_test_changespec(name="parent_cl")
    reverted_child = _create_test_changespec(
        name="child_cl__1", parent="parent_cl", status="Reverted"
    )

    with patch(
        "search.split_workflow.utils.find_all_changespecs",
        return_value=[parent, reverted_child],
    ):
        assert has_children("parent_cl") is False


def test_get_editor_from_env() -> None:
    """Test get_editor uses EDITOR environment variable."""
    with patch.dict(os.environ, {"EDITOR": "nano"}):
        assert get_editor() == "nano"


def test_get_editor_fallback_to_vim() -> None:
    """Test get_editor falls back to vim when nvim not available."""
    with patch.dict(os.environ, {}, clear=True):
        # Clear EDITOR
        if "EDITOR" in os.environ:
            del os.environ["EDITOR"]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)  # nvim not found
            editor = get_editor()
            assert editor == "vim"


def test_split_workflow_init() -> None:
    """Test SplitWorkflow initialization."""
    workflow = SplitWorkflow(
        name="my_feature",
        spec_path="/path/to/spec.yml",
        create_spec=False,
    )

    assert workflow._cl_name == "my_feature"
    assert workflow._spec_path == "/path/to/spec.yml"
    assert workflow._create_spec is False


def test_split_workflow_name_property() -> None:
    """Test SplitWorkflow.name property."""
    workflow = SplitWorkflow(name=None, spec_path=None, create_spec=True)
    assert workflow.name == "split"


def test_split_workflow_description_property() -> None:
    """Test SplitWorkflow.description property."""
    workflow = SplitWorkflow(name=None, spec_path=None, create_spec=True)
    assert workflow.description == "Split a CL into multiple smaller CLs"


def test_extract_yaml_from_response_with_code_fence() -> None:
    """Test extracting YAML from markdown code fence."""
    response = """Here is the split specification:

```yaml
- name: test_cl
  description: Test description
```

That's the spec."""
    result = _extract_yaml_from_response(response)
    assert result == "- name: test_cl\n  description: Test description"


def test_extract_yaml_from_response_with_yml_fence() -> None:
    """Test extracting YAML from yml code fence."""
    response = """```yml
- name: my_change
  description: My change
```"""
    result = _extract_yaml_from_response(response)
    assert result == "- name: my_change\n  description: My change"


def test_extract_yaml_from_response_no_fence() -> None:
    """Test extracting YAML when no code fence is present."""
    response = """- name: plain_yaml
  description: No fence here"""
    result = _extract_yaml_from_response(response)
    assert result == "- name: plain_yaml\n  description: No fence here"


def test_extract_yaml_from_response_strips_whitespace() -> None:
    """Test that whitespace is stripped from response."""
    response = """

  - name: whitespace_test
    description: Has whitespace

  """
    result = _extract_yaml_from_response(response)
    assert result.startswith("- name: whitespace_test")

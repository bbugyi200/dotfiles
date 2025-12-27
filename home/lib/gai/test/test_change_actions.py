"""Tests for change_actions module."""

import os
import tempfile

from change_actions import _delete_proposal_entry


def test_delete_proposal_entry_success() -> None:
    """Test deleting a proposal entry from a project file."""
    project_content = """NAME: my_feature
DESCRIPTION:
  Test description
STATUS: Drafted
HISTORY:
  (1) Initial commit
      | DIFF: ~/.gai/diffs/my_feature_123.diff
  (1a) [fix typo]
      | DIFF: ~/.gai/diffs/my_feature_fix.diff
  (1b) [add test]
      | DIFF: ~/.gai/diffs/my_feature_test.diff
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(project_content)
        project_file = f.name

    try:
        # Delete proposal 1a
        result = _delete_proposal_entry(project_file, "my_feature", 1, "a")
        assert result is True

        # Read back and verify
        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        assert "(1a) [fix typo]" not in content
        assert "(1) Initial commit" in content
        assert "(1b) [add test]" in content
    finally:
        os.unlink(project_file)


def test_delete_proposal_entry_not_found() -> None:
    """Test deleting a proposal that doesn't exist."""
    project_content = """NAME: my_feature
DESCRIPTION:
  Test description
STATUS: Drafted
HISTORY:
  (1) Initial commit
      | DIFF: ~/.gai/diffs/my_feature_123.diff
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(project_content)
        project_file = f.name

    try:
        # Try to delete non-existent proposal
        result = _delete_proposal_entry(project_file, "my_feature", 2, "a")
        # Should still return True (no entry to delete, but file was processed)
        assert result is True
    finally:
        os.unlink(project_file)


def test_delete_proposal_entry_file_not_found() -> None:
    """Test deleting from a non-existent file."""
    result = _delete_proposal_entry("/nonexistent/path/file.gp", "my_feature", 1, "a")
    assert result is False


def test_delete_proposal_entry_wrong_cl_name() -> None:
    """Test that we don't delete entries from wrong ChangeSpec."""
    project_content = """NAME: feature_a
HISTORY:
  (1a) [fix]
      | DIFF: ~/.gai/diffs/a.diff

NAME: feature_b
HISTORY:
  (1a) [fix]
      | DIFF: ~/.gai/diffs/b.diff
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(project_content)
        project_file = f.name

    try:
        # Delete 1a from feature_a only
        result = _delete_proposal_entry(project_file, "feature_a", 1, "a")
        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # feature_a's 1a should be deleted
        lines = content.split("\n")
        in_feature_a = False
        in_feature_b = False
        found_1a_in_a = False
        found_1a_in_b = False

        for line in lines:
            if "NAME: feature_a" in line:
                in_feature_a = True
                in_feature_b = False
            elif "NAME: feature_b" in line:
                in_feature_a = False
                in_feature_b = True
            elif "(1a)" in line:
                if in_feature_a:
                    found_1a_in_a = True
                if in_feature_b:
                    found_1a_in_b = True

        # feature_a's 1a should be gone, feature_b's 1a should remain
        assert found_1a_in_a is False
        assert found_1a_in_b is True
    finally:
        os.unlink(project_file)

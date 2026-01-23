"""Tests for commit_workflow.changespec_operations module."""

import os
import tempfile
from unittest.mock import patch

from ace.changespec.parser import parse_project_file
from commit_workflow.changespec_operations import add_changespec_to_project_file


def test_add_changespec_with_initial_hooks() -> None:
    """Test that initial_hooks are included in the ChangeSpec block."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                initial_hooks=["!$bb_hg_presubmit", "bb_hg_lint"],
            )

        assert result is not None

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify hooks are present
        assert "HOOKS:" in content
        assert "  !$bb_hg_presubmit" in content
        assert "  bb_hg_lint" in content
    finally:
        os.unlink(project_file)


def test_add_changespec_without_initial_hooks() -> None:
    """Test that ChangeSpec works without initial_hooks (backward compatible)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                # No initial_hooks parameter - backward compatible
            )

        assert result is not None

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify HOOKS is NOT present when not provided
        assert "HOOKS:" not in content
    finally:
        os.unlink(project_file)


def test_add_changespec_hooks_in_correct_order() -> None:
    """Test that hooks appear in the correct order in the ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                initial_hooks=[
                    "!$bb_hg_presubmit",
                    "bb_hg_lint",
                    "bb_rabbit_test //foo:test1",
                ],
            )

        assert result is not None

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify order (presubmit before lint before test target)
        presubmit_idx = content.index("!$bb_hg_presubmit")
        lint_idx = content.index("bb_hg_lint")
        test_idx = content.index("bb_rabbit_test")
        assert presubmit_idx < lint_idx < test_idx
    finally:
        os.unlink(project_file)


def test_add_changespec_with_empty_hooks_list() -> None:
    """Test that empty initial_hooks list doesn't add HOOKS field."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                initial_hooks=[],  # Empty list
            )

        assert result is not None

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify HOOKS is NOT present when list is empty
        assert "HOOKS:" not in content
    finally:
        os.unlink(project_file)


def test_add_changespec_with_bug_field() -> None:
    """Test that BUG field is included in the ChangeSpec block."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                bug="http://b/12345678",
            )

        assert result is not None

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify BUG field is present with correct format
        assert "BUG: http://b/12345678" in content
    finally:
        os.unlink(project_file)


def test_add_changespec_without_bug_field() -> None:
    """Test that no BUG field is added when bug is None."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                # No bug parameter
            )

        assert result is not None

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify BUG field is NOT present
        assert "BUG:" not in content
    finally:
        os.unlink(project_file)


def test_parse_changespec_with_bug_field() -> None:
    """Test that BUG field is correctly parsed from ChangeSpec."""
    content = """NAME: test_feature
DESCRIPTION:
  Test description
BUG: http://b/12345678
CL: http://cl/12345
STATUS: WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        project_file = f.name

    try:
        changespecs = parse_project_file(project_file)
        assert len(changespecs) == 1
        cs = changespecs[0]
        assert cs.name == "test_feature"
        assert cs.bug == "http://b/12345678"
    finally:
        os.unlink(project_file)


def test_parse_changespec_without_bug_field() -> None:
    """Test that ChangeSpec without BUG field has bug=None."""
    content = """NAME: test_feature
DESCRIPTION:
  Test description
CL: http://cl/12345
STATUS: WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        project_file = f.name

    try:
        changespecs = parse_project_file(project_file)
        assert len(changespecs) == 1
        cs = changespecs[0]
        assert cs.name == "test_feature"
        assert cs.bug is None
    finally:
        os.unlink(project_file)


def test_add_changespec_inherits_parent_hooks() -> None:
    """Test that child ChangeSpec inherits hooks from parent."""
    # Create a project file with a parent ChangeSpec containing hooks
    parent_content = """NAME: parent_feature
DESCRIPTION:
  Parent description
CL: http://cl/11111
STATUS: WIP
HOOKS:
  !$bb_hg_presubmit
  bb_hg_lint
  bb_rabbit_test //foo:parent_test
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(parent_content)
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="child_feature",
                description="Child description",
                parent="parent_feature",
                cl_url="http://cl/22222",
                # initial_hooks contains !$bb_hg_presubmit (should NOT be duplicated)
                initial_hooks=["!$bb_hg_presubmit"],
            )

        assert result is not None

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify child ChangeSpec exists
        assert "NAME: child_feature__1" in content

        # Parse to verify hooks - find the child ChangeSpec
        changespecs = parse_project_file(project_file)
        child_cs = next(cs for cs in changespecs if cs.name == "child_feature__1")
        assert child_cs.hooks is not None

        # Get hook commands from the child
        child_hooks = [h.command for h in child_cs.hooks]

        # Should have: initial hook + inherited parent hooks (minus duplicate)
        assert "!$bb_hg_presubmit" in child_hooks  # From initial_hooks
        assert "bb_hg_lint" in child_hooks  # Inherited from parent
        assert "bb_rabbit_test //foo:parent_test" in child_hooks  # Inherited

        # !$bb_hg_presubmit should NOT be duplicated
        assert child_hooks.count("!$bb_hg_presubmit") == 1
    finally:
        os.unlink(project_file)


def test_add_changespec_inherits_parent_hooks_order() -> None:
    """Test that inherited parent hooks come after initial hooks."""
    parent_content = """NAME: parent_feature
DESCRIPTION:
  Parent description
CL: http://cl/11111
STATUS: WIP
HOOKS:
  bb_hg_lint
  bb_rabbit_test //foo:parent_test
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(parent_content)
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="child_feature",
                description="Child description",
                parent="parent_feature",
                cl_url="http://cl/22222",
                initial_hooks=["!$bb_hg_presubmit", "bb_rabbit_test //foo:child_test"],
            )

        assert result is not None

        # Parse to verify hook order
        changespecs = parse_project_file(project_file)
        child_cs = next(cs for cs in changespecs if cs.name == "child_feature__1")
        assert child_cs.hooks is not None
        child_hooks = [h.command for h in child_cs.hooks]

        # Order should be: initial hooks first, then inherited parent hooks
        assert child_hooks == [
            "!$bb_hg_presubmit",  # From initial_hooks
            "bb_rabbit_test //foo:child_test",  # From initial_hooks
            "bb_hg_lint",  # Inherited from parent
            "bb_rabbit_test //foo:parent_test",  # Inherited from parent
        ]
    finally:
        os.unlink(project_file)


def test_add_changespec_no_parent_hooks_inherited_when_no_parent() -> None:
    """Test that no hooks are inherited when there's no parent."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="orphan_feature",
                description="Orphan description",
                parent=None,  # No parent
                cl_url="http://cl/33333",
                initial_hooks=["!$bb_hg_presubmit"],
            )

        assert result is not None

        changespecs = parse_project_file(project_file)
        cs = changespecs[0]
        assert cs.hooks is not None
        child_hooks = [h.command for h in cs.hooks]

        # Should only have initial hooks
        assert child_hooks == ["!$bb_hg_presubmit"]
    finally:
        os.unlink(project_file)


def test_add_changespec_inherits_parent_bug() -> None:
    """Test that child ChangeSpec inherits BUG from parent."""
    # Create a project file with a parent ChangeSpec containing BUG
    parent_content = """NAME: parent_feature
DESCRIPTION:
  Parent description
BUG: http://b/12345678
CL: http://cl/11111
STATUS: WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(parent_content)
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="child_feature",
                description="Child description",
                parent="parent_feature",
                cl_url="http://cl/22222",
                # No bug parameter - should inherit from parent
            )

        assert result is not None

        # Parse to verify BUG inheritance
        changespecs = parse_project_file(project_file)
        child_cs = next(cs for cs in changespecs if cs.name == "child_feature__1")

        # Child should have inherited parent's BUG
        assert child_cs.bug == "http://b/12345678"
    finally:
        os.unlink(project_file)


def test_add_changespec_explicit_bug_overrides_parent() -> None:
    """Test that explicit bug parameter takes precedence over parent's BUG."""
    # Create a project file with a parent ChangeSpec containing BUG
    parent_content = """NAME: parent_feature
DESCRIPTION:
  Parent description
BUG: http://b/11111111
CL: http://cl/11111
STATUS: WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(parent_content)
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="child_feature",
                description="Child description",
                parent="parent_feature",
                cl_url="http://cl/22222",
                bug="http://b/99999999",  # Explicit bug should override parent
            )

        assert result is not None

        # Parse to verify explicit BUG takes precedence
        changespecs = parse_project_file(project_file)
        child_cs = next(cs for cs in changespecs if cs.name == "child_feature__1")

        # Child should have its explicit BUG, not parent's
        assert child_cs.bug == "http://b/99999999"
    finally:
        os.unlink(project_file)


def test_add_changespec_no_parent_bug_inherited_when_no_parent() -> None:
    """Test that no BUG is inherited when there's no parent."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="orphan_feature",
                description="Orphan description",
                parent=None,  # No parent
                cl_url="http://cl/33333",
                # No bug parameter
            )

        assert result is not None

        changespecs = parse_project_file(project_file)
        cs = changespecs[0]

        # Should have no BUG since no parent and no explicit bug
        assert cs.bug is None
    finally:
        os.unlink(project_file)

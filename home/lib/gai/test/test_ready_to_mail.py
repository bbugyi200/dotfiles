"""Tests for check_ready_to_mail in suffix transforms."""

from unittest.mock import patch

from ace.changespec import ChangeSpec, CommentEntry, HookEntry, HookStatusLine
from ace.loop.suffix_transforms import check_ready_to_mail


def _make_changespec(
    name: str = "test_cs",
    status: str = "Drafted",
    file_path: str = "/path/to/project.gp",
    hooks: list[HookEntry] | None = None,
    comments: list[CommentEntry] | None = None,
) -> ChangeSpec:
    """Create a ChangeSpec for loop workflow testing."""
    return ChangeSpec(
        name=name,
        description="Test description",
        parent=None,
        cl="http://cl/12345",
        status=status,
        test_targets=None,
        kickstart=None,
        file_path=file_path,
        line_number=1,
        commits=None,
        hooks=hooks,
        comments=comments,
    )


def test_check_ready_to_mail_adds_suffix_for_drafted_no_errors() -> None:
    """Test check_ready_to_mail adds suffix for Drafted status with no errors."""
    changespec = _make_changespec(status="Drafted")
    all_changespecs = [changespec]

    with patch(
        "ace.loop.suffix_transforms.add_ready_to_mail_suffix", return_value=True
    ):
        result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 1
    assert "Added READY TO MAIL suffix" in result[0]


def test_check_ready_to_mail_skips_non_drafted_status() -> None:
    """Test check_ready_to_mail skips non-Drafted statuses."""
    changespec = _make_changespec(status="Mailed")
    all_changespecs = [changespec]

    result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 0


def test_check_ready_to_mail_skips_already_has_suffix() -> None:
    """Test check_ready_to_mail skips if suffix already present."""
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)")
    all_changespecs = [changespec]

    result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 0


def test_check_ready_to_mail_skips_with_error_suffix_in_hooks() -> None:
    """Test check_ready_to_mail skips if hook has error suffix."""
    hook = HookEntry(
        command="make lint",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="241228_120000",
                status="FAILED",
                suffix="Hook Command Failed",
                suffix_type="error",
            )
        ],
    )
    changespec = _make_changespec(status="Drafted", hooks=[hook])
    all_changespecs = [changespec]

    result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 0


def test_check_ready_to_mail_skips_parent_not_ready() -> None:
    """Test check_ready_to_mail skips if parent is not ready."""
    parent = _make_changespec(name="parent_cs", status="Drafted")
    child = ChangeSpec(
        name="child_cs",
        description="Test description",
        parent="parent_cs",
        cl="http://cl/12346",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
        commits=None,
        hooks=None,
        comments=None,
    )
    all_changespecs = [parent, child]

    result = check_ready_to_mail(child, all_changespecs)

    assert len(result) == 0


def test_check_ready_to_mail_allows_parent_submitted() -> None:
    """Test check_ready_to_mail allows when parent is Submitted."""
    parent = _make_changespec(name="parent_cs", status="Submitted")
    child = ChangeSpec(
        name="child_cs",
        description="Test description",
        parent="parent_cs",
        cl="http://cl/12346",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
        commits=None,
        hooks=None,
        comments=None,
    )
    all_changespecs = [parent, child]

    with patch(
        "ace.loop.suffix_transforms.add_ready_to_mail_suffix", return_value=True
    ):
        result = check_ready_to_mail(child, all_changespecs)

    assert len(result) == 1
    assert "Added READY TO MAIL suffix" in result[0]


def test_check_ready_to_mail_skips_parent_with_only_suffix() -> None:
    """Test check_ready_to_mail skips when parent only has READY TO MAIL suffix.

    Parent must be Mailed or Submitted, not just have the READY TO MAIL suffix.
    """
    parent = _make_changespec(name="parent_cs", status="Drafted - (!: READY TO MAIL)")
    child = ChangeSpec(
        name="child_cs",
        description="Test description",
        parent="parent_cs",
        cl="http://cl/12346",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
        commits=None,
        hooks=None,
        comments=None,
    )
    all_changespecs = [parent, child]

    result = check_ready_to_mail(child, all_changespecs)

    # Suffix should NOT be added because parent is not Mailed or Submitted
    assert len(result) == 0


def test_check_ready_to_mail_removes_suffix_when_error_appears() -> None:
    """Test check_ready_to_mail removes suffix when error suffix appears."""
    hook = HookEntry(
        command="make lint",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="241228_120000",
                status="FAILED",
                suffix="Hook Command Failed",
                suffix_type="error",
            )
        ],
    )
    # ChangeSpec has READY TO MAIL suffix but now has an error
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)", hooks=[hook])
    all_changespecs = [changespec]

    with patch(
        "ace.loop.suffix_transforms.remove_ready_to_mail_suffix", return_value=True
    ):
        result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 1
    assert "Removed READY TO MAIL suffix (error suffix appeared)" in result[0]


def test_check_ready_to_mail_removes_suffix_when_parent_not_ready() -> None:
    """Test check_ready_to_mail removes suffix when parent is no longer ready."""
    # Parent no longer has READY TO MAIL suffix and is still Drafted
    parent = _make_changespec(name="parent_cs", status="Drafted")
    # Child has the suffix but parent is not ready anymore
    child = ChangeSpec(
        name="child_cs",
        description="Test description",
        parent="parent_cs",
        cl="http://cl/12346",
        status="Drafted - (!: READY TO MAIL)",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
        commits=None,
        hooks=None,
        comments=None,
    )
    all_changespecs = [parent, child]

    with patch(
        "ace.loop.suffix_transforms.remove_ready_to_mail_suffix", return_value=True
    ):
        result = check_ready_to_mail(child, all_changespecs)

    assert len(result) == 1
    assert "Removed READY TO MAIL suffix (parent no longer ready)" in result[0]


def test_check_ready_to_mail_keeps_suffix_when_conditions_still_met() -> None:
    """Test check_ready_to_mail keeps suffix when conditions are still met."""
    # ChangeSpec has suffix and conditions are still met (no parent, no errors)
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)")
    all_changespecs = [changespec]

    result = check_ready_to_mail(changespec, all_changespecs)

    # No updates - suffix should remain
    assert len(result) == 0

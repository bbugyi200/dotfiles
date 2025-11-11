"""Tests for mail_ops module."""

from work.mail_ops import _modify_description_for_mailing


def test_modify_description_one_reviewer_no_parent() -> None:
    """Test scenario 1: 1 reviewer, no valid parent."""
    description = """This is a test CL.

It does something cool.

R=startblock
Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(description, ["reviewer1"], False, None)

    assert "R=reviewer1" in result
    assert "R=startblock" not in result
    assert "Startblock Conditions" not in result
    assert "Bug: b/12345" in result


def test_modify_description_one_reviewer_with_parent() -> None:
    """Test scenario 2: 1 reviewer, valid parent."""
    description = """This is a test CL.

R=startblock
Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(description, ["reviewer1"], True, "123456")

    assert "R=reviewer1,startblock" in result
    assert "### Startblock Conditions" in result
    assert "cl/123456 has LGTM" in result
    assert "add reviewer reviewer1" in result
    assert "Bug: b/12345" in result


def test_modify_description_two_reviewers_no_parent() -> None:
    """Test scenario 3: 2 reviewers, no valid parent."""
    description = """This is a test CL.

R=startblock
Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(
        description, ["reviewer1", "reviewer2"], False, None
    )

    assert "R=reviewer1,startblock" in result
    assert "### Startblock Conditions" in result
    assert "has LGTM from reviewer1" in result
    assert "add reviewer reviewer2" in result
    assert "Bug: b/12345" in result


def test_modify_description_two_reviewers_with_parent() -> None:
    """Test scenario 4: 2 reviewers, valid parent."""
    description = """This is a test CL.

R=startblock
Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(
        description, ["reviewer1", "reviewer2"], True, "123456"
    )

    assert "### Startblock Conditions" in result
    assert "cl/123456 has LGTM" in result
    assert "add reviewer reviewer1" in result
    assert "has LGTM from reviewer1" in result
    assert "add reviewer reviewer2" in result
    assert "Bug: b/12345" in result


def test_modify_description_preserves_tags() -> None:
    """Test that tags are preserved at the end of description."""
    description = """This is a test CL.

R=startblock
Bug: b/12345
Test: manual
Change-Id: I1234567890abcdef"""

    result = _modify_description_for_mailing(description, ["reviewer1"], False, None)

    assert "Bug: b/12345" in result
    assert "Test: manual" in result
    assert "Change-Id: I1234567890abcdef" in result
    # Tags should be at the end
    lines = result.split("\n")
    assert "Change-Id:" in lines[-1]


def test_modify_description_with_multiline_content() -> None:
    """Test handling of multiline descriptions."""
    description = """This is a long CL description.

It spans multiple lines.

And has multiple paragraphs.

R=startblock
Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(description, ["reviewer1"], False, None)

    assert "This is a long CL description" in result
    assert "It spans multiple lines" in result
    assert "And has multiple paragraphs" in result
    assert "R=reviewer1" in result


def test_modify_description_startblock_section_placement() -> None:
    """Test that Startblock section is placed before tags."""
    description = """This is a test CL.

R=startblock
Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(description, ["reviewer1"], True, "123456")

    lines = result.split("\n")
    startblock_idx = None
    bug_idx = None

    for i, line in enumerate(lines):
        if "### Startblock Conditions" in line:
            startblock_idx = i
        if "Bug:" in line:
            bug_idx = i

    assert startblock_idx is not None
    assert bug_idx is not None
    assert startblock_idx < bug_idx, "Startblock section should come before tags"


def test_modify_description_with_r_line_not_on_separate_line() -> None:
    """Test handling when R= is in the middle of content."""
    description = """This is a test CL.
R=startblock

Some more text here.

Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(description, ["reviewer1"], False, None)

    assert "R=reviewer1" in result
    assert "Some more text here" in result


def test_modify_description_blank_lines_preserved() -> None:
    """Test that structure with blank lines is preserved."""
    description = """This is a test CL.

Second paragraph.


Third paragraph with double blank line above.

R=startblock
Bug: b/12345"""

    result = _modify_description_for_mailing(description, ["reviewer1"], False, None)

    # The blank lines should be somewhat preserved in the structure
    assert "Second paragraph" in result
    assert "Third paragraph" in result

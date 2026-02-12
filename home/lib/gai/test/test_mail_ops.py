"""Tests for mail_ops module."""

from ace.mail_ops import (
    MailPrepResult,
    _modify_description_for_mailing,
    escape_for_hg_reword,
    normalize_cl_tags,
)


def test_mail_prep_result_should_mail_true() -> None:
    """Test MailPrepResult dataclass with should_mail=True."""
    result = MailPrepResult(should_mail=True)
    assert result.should_mail is True


def test_mail_prep_result_should_mail_false() -> None:
    """Test MailPrepResult dataclass with should_mail=False."""
    result = MailPrepResult(should_mail=False)
    assert result.should_mail is False


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
    """Test scenario 2: 1 reviewer, valid parent.

    When there's a valid parent, R= should remain as "R=startblock" and the
    reviewer will be added later by the startblock system.
    """
    description = """This is a test CL.

R=startblock
Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(description, ["reviewer1"], True, "123456")

    assert "R=startblock" in result
    assert "R=reviewer1,startblock" not in result  # Should NOT add reviewer to R= tag
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


def test_modify_description_body_content_matching_tag_pattern() -> None:
    """Test that body content like 'Screenshots: ...' is not mistaken for a footer tag.

    Regression test: The tag-finding logic used to scan top-down and would match
    body lines like 'Screenshots: [before][1]' as tags, causing the startblock
    section to be inserted between the title and body instead of before the
    actual footer tags.
    """
    description = """[pat] Fix rendering bug

Screenshots: [before][1]
See also: http://example.com

R=startblock
Bug: b/12345
Test: manual"""

    result = _modify_description_for_mailing(description, ["reviewer1"], True, "123456")

    lines = result.split("\n")
    screenshots_idx = None
    startblock_idx = None
    bug_idx = None

    for i, line in enumerate(lines):
        if "Screenshots:" in line:
            screenshots_idx = i
        if "### Startblock Conditions" in line:
            startblock_idx = i
        if "Bug:" in line:
            bug_idx = i

    assert screenshots_idx is not None
    assert startblock_idx is not None
    assert bug_idx is not None
    assert screenshots_idx < startblock_idx, "Screenshots should come before startblock"
    assert startblock_idx < bug_idx, "Startblock section should come before footer tags"


def test_modify_description_with_key_value_tags() -> None:
    """Test handling of KEY=value format tags (e.g., BUG=, R=, MARKDOWN=)."""
    description = """[pat] Test CL with KEY=value tags

This is a test description.

AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT
BUG=12345
R=startblock
MARKDOWN=true
STARTBLOCK_AUTOSUBMIT=yes
WANT_LGTM=all"""

    result = _modify_description_for_mailing(description, ["reviewer1"], True, "123456")

    # Check that startblock section comes before tags
    lines = result.split("\n")
    startblock_idx = None
    bug_idx = None

    for i, line in enumerate(lines):
        if "### Startblock Conditions" in line:
            startblock_idx = i
        if "BUG=" in line:
            bug_idx = i

    assert startblock_idx is not None
    assert bug_idx is not None
    assert startblock_idx < bug_idx, "Startblock before tags"

    # Check that R=startblock is preserved (not changed to R=reviewer1,startblock)
    assert "R=startblock" in result
    assert "R=reviewer1,startblock" not in result

    # Check that all tags are preserved
    assert "AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT" in result
    assert "BUG=12345" in result
    assert "MARKDOWN=true" in result
    assert "STARTBLOCK_AUTOSUBMIT=yes" in result
    assert "WANT_LGTM=all" in result


def test_normalize_cl_tags_splits_multiple_tags_on_one_line() -> None:
    """Test that multiple KEY=value tags on one line get split."""
    description = (
        "Fix rendering bug\n"
        "\n"
        "AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT BUG=350330301 R=startblock "
        "MARKDOWN=true STARTBLOCK_AUTOSUBMIT=yes WANT_LGTM=all"
    )
    result = normalize_cl_tags(description)
    assert result == (
        "Fix rendering bug\n"
        "\n"
        "AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT\n"
        "BUG=350330301\n"
        "R=startblock\n"
        "MARKDOWN=true\n"
        "STARTBLOCK_AUTOSUBMIT=yes\n"
        "WANT_LGTM=all"
    )


def test_normalize_cl_tags_preserves_value_with_spaces() -> None:
    """Test that a single tag whose value contains spaces is not split."""
    description = (
        "Fix bug\n\nNO_RELNOTES=The YieldPartner and YieldGroup OP services\nBUG=12345"
    )
    result = normalize_cl_tags(description)
    assert result == description


def test_normalize_cl_tags_noop_when_already_separate() -> None:
    """Test no-op when tags are already on separate lines."""
    description = (
        "Fix bug\n\nAUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT\nBUG=350330301\nR=startblock"
    )
    result = normalize_cl_tags(description)
    assert result == description


def test_normalize_cl_tags_no_tags() -> None:
    """Test description with no tags at all."""
    description = "Fix rendering bug\n\nThis is just a description."
    result = normalize_cl_tags(description)
    assert result == description


def test_escape_for_hg_reword_newlines() -> None:
    """Test that actual newlines are escaped to literal \\n."""
    assert escape_for_hg_reword("line1\nline2") == "line1\\nline2"


def test_escape_for_hg_reword_tabs() -> None:
    """Test that actual tabs are escaped to literal \\t."""
    assert escape_for_hg_reword("col1\tcol2") == "col1\\tcol2"


def test_escape_for_hg_reword_single_quotes() -> None:
    """Test that single quotes are escaped."""
    assert escape_for_hg_reword("it's") == "it\\'s"


def test_escape_for_hg_reword_backslashes() -> None:
    """Test that backslashes are escaped and ordering is correct.

    Backslashes must be escaped before newlines, otherwise a literal
    backslash followed by 'n' would become '\\\\n' instead of '\\\\n'.
    """
    assert escape_for_hg_reword("path\\to") == "path\\\\to"
    # Verify ordering: backslash-then-n should NOT become \\n (escaped newline)
    assert escape_for_hg_reword("\\n") == "\\\\n"


def test_escape_for_hg_reword_carriage_returns() -> None:
    """Test that carriage returns are escaped to literal \\r."""
    assert escape_for_hg_reword("line1\rline2") == "line1\\rline2"


def test_escape_for_hg_reword_no_special_chars() -> None:
    """Test that strings without special chars pass through unchanged."""
    plain = "A simple description with no special characters."
    assert escape_for_hg_reword(plain) == plain


def test_escape_for_hg_reword_mixed_content() -> None:
    """Test a realistic multi-line description with mixed special chars."""
    description = "Fix the bug\n\nDetails:\n\tUse 'new' approach\\old"
    expected = "Fix the bug\\n\\nDetails:\\n\\tUse \\'new\\' approach\\\\old"
    assert escape_for_hg_reword(description) == expected

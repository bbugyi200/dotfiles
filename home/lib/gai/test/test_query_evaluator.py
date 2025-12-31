"""Tests for evaluating parsed queries against ChangeSpec objects."""

from typing import Any

from ace.changespec import (
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
)
from ace.query import evaluate_query, parse_query


def test_evaluate_string_match_case_insensitive(make_changespec: Any) -> None:
    """Test case-insensitive string matching."""
    query = parse_query('"feature"')
    cs = make_changespec.create(name="my_FEATURE_test")
    assert evaluate_query(query, cs) is True


def test_evaluate_string_match_case_sensitive(
    make_changespec: Any,
) -> None:
    """Test case-sensitive string matching."""
    query = parse_query('c"Feature"')
    cs = make_changespec.create(name="my_Feature_test")
    assert evaluate_query(query, cs) is True

    cs2 = make_changespec.create(name="my_feature_test")
    assert evaluate_query(query, cs2) is False


def test_evaluate_not_match(make_changespec: Any) -> None:
    """Test NOT expression evaluation."""
    query = parse_query('!"draft"')
    # Use status="Mailed" to avoid default "Drafted" status containing "draft"
    cs1 = make_changespec.create(name="my_feature", status="Mailed")
    assert evaluate_query(query, cs1) is True

    cs2 = make_changespec.create(name="draft_feature", status="Mailed")
    assert evaluate_query(query, cs2) is False


def test_evaluate_and_match(make_changespec: Any) -> None:
    """Test AND expression evaluation."""
    query = parse_query('"feature" AND "test"')
    cs1 = make_changespec.create(name="feature", description="test code")
    assert evaluate_query(query, cs1) is True

    cs2 = make_changespec.create(name="feature", description="production")
    assert evaluate_query(query, cs2) is False


def test_evaluate_or_match(make_changespec: Any) -> None:
    """Test OR expression evaluation."""
    query = parse_query('"feature" OR "bugfix"')
    cs1 = make_changespec.create(name="my_feature")
    assert evaluate_query(query, cs1) is True

    cs2 = make_changespec.create(name="my_bugfix")
    assert evaluate_query(query, cs2) is True

    cs3 = make_changespec.create(name="refactor")
    assert evaluate_query(query, cs3) is False


def test_evaluate_complex_query(make_changespec: Any) -> None:
    """Test complex query evaluation."""
    query = parse_query('("feature" OR "bugfix") AND !"skip"')

    cs1 = make_changespec.create(name="my_feature")
    assert evaluate_query(query, cs1) is True

    cs2 = make_changespec.create(name="skip_feature")
    assert evaluate_query(query, cs2) is False

    cs3 = make_changespec.create(name="refactor")
    assert evaluate_query(query, cs3) is False


def test_evaluate_matches_status(make_changespec: Any) -> None:
    """Test matching against status field."""
    query = parse_query('"Drafted"')
    cs = make_changespec.create(status="Drafted")
    assert evaluate_query(query, cs) is True


def test_evaluate_matches_project(make_changespec: Any) -> None:
    """Test matching against project basename."""
    query = parse_query('"myproject"')
    cs = make_changespec.create(
        file_path="/home/user/.gai/projects/myproject/myproject.gp"
    )
    assert evaluate_query(query, cs) is True


def test_evaluate_matches_description(
    make_changespec: Any,
) -> None:
    """Test matching against description."""
    query = parse_query('"important fix"')
    cs = make_changespec.create(description="This is an important fix for the bug")
    assert evaluate_query(query, cs) is True


def test_evaluate_error_suffix_matches_status_with_error(
    make_changespec: Any,
) -> None:
    """Test !!! matches ChangeSpec with error suffix in status."""
    query = parse_query("!!!")
    cs = make_changespec.create(status="Drafted - (!: ZOMBIE)")
    assert evaluate_query(query, cs) is True


def test_evaluate_error_suffix_matches_ready_to_mail(
    make_changespec: Any,
) -> None:
    """Test !!! matches ChangeSpec with READY TO MAIL suffix."""
    query = parse_query("!!!")
    cs = make_changespec.create(status="Drafted - (!: READY TO MAIL)")
    assert evaluate_query(query, cs) is True


def test_evaluate_error_suffix_no_match_plain_status(
    make_changespec: Any,
) -> None:
    """Test !!! does not match ChangeSpec without error suffix format."""
    query = parse_query("!!!")
    cs = make_changespec.create(status="Drafted")
    assert evaluate_query(query, cs) is False


def test_evaluate_error_suffix_combined_with_project(
    make_changespec: Any,
) -> None:
    """Test !!! AND myproject matches correctly."""
    query = parse_query("!!! AND myproject")
    cs = make_changespec.create(
        status="Drafted - (!: ZOMBIE)",
        file_path="/home/user/.gai/projects/myproject/myproject.gp",
    )
    assert evaluate_query(query, cs) is True


def test_evaluate_no_status_suffix_excludes_error_status(
    make_changespec: Any,
) -> None:
    """Test !! excludes ChangeSpec with error suffix in status."""
    query = parse_query("!!")
    cs = make_changespec.create(status="Drafted - (!: ZOMBIE)")
    assert evaluate_query(query, cs) is False


def test_evaluate_no_status_suffix_excludes_ready_to_mail(
    make_changespec: Any,
) -> None:
    """Test !! excludes ChangeSpec with READY TO MAIL suffix in status."""
    query = parse_query("!!")
    cs = make_changespec.create(status="Drafted - (!: READY TO MAIL)")
    assert evaluate_query(query, cs) is False


def test_evaluate_no_status_suffix_includes_plain_status(
    make_changespec: Any,
) -> None:
    """Test !! includes ChangeSpec without any status suffix."""
    query = parse_query("!!")
    cs = make_changespec.create(status="Drafted")
    assert evaluate_query(query, cs) is True


def test_evaluate_no_status_suffix_combined_with_project(
    make_changespec: Any,
) -> None:
    """Test !! AND myproject excludes any status suffix for myproject."""
    query = parse_query("!! AND myproject")
    # Error status for myproject - should not match
    cs1 = make_changespec.create(
        status="Drafted - (!: ZOMBIE)",
        file_path="/home/user/.gai/projects/myproject/myproject.gp",
    )
    assert evaluate_query(query, cs1) is False

    # READY TO MAIL status for myproject - should not match
    cs2 = make_changespec.create(
        status="Drafted - (!: READY TO MAIL)",
        file_path="/home/user/.gai/projects/myproject/myproject.gp",
    )
    assert evaluate_query(query, cs2) is False

    # Plain status for myproject - should match
    cs3 = make_changespec.create(
        status="Drafted",
        file_path="/home/user/.gai/projects/myproject/myproject.gp",
    )
    assert evaluate_query(query, cs3) is True


def test_evaluate_error_suffix_matches_history_suffix(
    make_changespec: Any,
) -> None:
    """Test !!! matches ChangeSpec with suffix in HISTORY entry."""
    query = parse_query("!!!")
    cs = make_changespec.create(
        status="Drafted",  # No suffix in status
        commits=[
            CommitEntry(
                number=1,
                note="Some note",
                suffix="NEW PROPOSAL",
                suffix_type="error",
            )
        ],
    )
    assert evaluate_query(query, cs) is True


def test_evaluate_error_suffix_matches_hook_suffix(
    make_changespec: Any,
) -> None:
    """Test !!! matches ChangeSpec with suffix in HOOKS status line."""
    query = parse_query("!!!")
    cs = make_changespec.create(
        status="Drafted",  # No suffix in status
        hooks=[
            HookEntry(
                command="bb_test",
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="251230_120000",
                        status="FAILED",
                        suffix="ZOMBIE",
                        suffix_type="error",
                    )
                ],
            )
        ],
    )
    assert evaluate_query(query, cs) is True


def test_evaluate_error_suffix_matches_comment_suffix(
    make_changespec: Any,
) -> None:
    """Test !!! matches ChangeSpec with suffix in COMMENTS entry."""
    query = parse_query("!!!")
    cs = make_changespec.create(
        status="Drafted",  # No suffix in status
        comments=[
            CommentEntry(
                reviewer="reviewer@example.com",
                file_path="~/.gai/comments/test.yml",
                suffix="UNREAD",
                suffix_type="error",
            )
        ],
    )
    assert evaluate_query(query, cs) is True


def test_evaluate_no_status_suffix_excludes_history_suffix(
    make_changespec: Any,
) -> None:
    """Test !! excludes ChangeSpec with suffix in HISTORY entry."""
    query = parse_query("!!")
    cs = make_changespec.create(
        status="Drafted",  # No suffix in status
        commits=[
            CommitEntry(
                number=1,
                note="Some note",
                suffix="NEW PROPOSAL",
                suffix_type="error",
            )
        ],
    )
    assert evaluate_query(query, cs) is False


def test_evaluate_no_status_suffix_excludes_hook_suffix(
    make_changespec: Any,
) -> None:
    """Test !! excludes ChangeSpec with suffix in HOOKS status line."""
    query = parse_query("!!")
    cs = make_changespec.create(
        status="Drafted",  # No suffix in status
        hooks=[
            HookEntry(
                command="bb_test",
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="251230_120000",
                        status="FAILED",
                        suffix="ZOMBIE",
                        suffix_type="error",
                    )
                ],
            )
        ],
    )
    assert evaluate_query(query, cs) is False


def test_evaluate_no_status_suffix_excludes_comment_suffix(
    make_changespec: Any,
) -> None:
    """Test !! excludes ChangeSpec with suffix in COMMENTS entry."""
    query = parse_query("!!")
    cs = make_changespec.create(
        status="Drafted",  # No suffix in status
        comments=[
            CommentEntry(
                reviewer="reviewer@example.com",
                file_path="~/.gai/comments/test.yml",
                suffix="UNREAD",
                suffix_type="error",
            )
        ],
    )
    assert evaluate_query(query, cs) is False


def test_evaluate_error_suffix_ignores_plain_hook_suffix(
    make_changespec: Any,
) -> None:
    """Test !!! does NOT match plain suffixes (without !: prefix) in hooks."""
    query = parse_query("!!!")
    cs = make_changespec.create(
        status="Drafted",  # No suffix in status
        hooks=[
            HookEntry(
                command="bb_test",
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="251230_120000",
                        status="FAILED",
                        suffix="CL 123456 presubmit failed",  # Plain suffix, no !:
                        suffix_type=None,  # Not an error suffix
                    )
                ],
            )
        ],
    )
    assert evaluate_query(query, cs) is False


def test_evaluate_error_suffix_ignores_plain_suffix(
    make_changespec: Any,
) -> None:
    """Test !!! does NOT match plain suffixes (no prefix) in history."""
    query = parse_query("!!!")
    cs = make_changespec.create(
        status="Drafted",  # No suffix in status
        commits=[
            CommitEntry(
                number=1,
                note="Some note",
                suffix="OLD PROPOSAL",
                suffix_type=None,  # plain suffix, not !:
            )
        ],
    )
    assert evaluate_query(query, cs) is False


def test_evaluate_no_status_suffix_includes_plain_hook_suffix(
    make_changespec: Any,
) -> None:
    """Test !! includes ChangeSpec with only plain suffixes (no error suffixes)."""
    query = parse_query("!!")
    cs = make_changespec.create(
        status="Drafted",  # No error suffix in status
        hooks=[
            HookEntry(
                command="bb_test",
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="251230_120000",
                        status="FAILED",
                        suffix="CL 123456 presubmit failed",  # Plain suffix
                        suffix_type=None,  # Not an error suffix
                    )
                ],
            )
        ],
    )
    # Should match because there are NO error suffixes
    assert evaluate_query(query, cs) is True

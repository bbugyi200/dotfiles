"""Tests for ace/loop/comments_handler.py - comment zombie detection."""

from typing import Any
from unittest.mock import MagicMock, patch

from ace.changespec import CommentEntry
from ace.scheduler.comments_handler import check_comment_zombies


# Tests for check_comment_zombies
def test_check_comment_zombies_no_comments(make_changespec: Any) -> None:
    """Test check_comment_zombies returns empty list when no comments."""
    cs = make_changespec.create(comments=None)
    result = check_comment_zombies(cs)
    assert result == []


def test_check_comment_zombies_empty_comments(make_changespec: Any) -> None:
    """Test check_comment_zombies returns empty list for empty comments list."""
    cs = make_changespec.create(comments=[])
    result = check_comment_zombies(cs)
    assert result == []


@patch("ace.scheduler.comments_handler.set_comment_suffix")
@patch("ace.scheduler.comments_handler.is_comments_suffix_stale")
def test_check_comment_zombies_no_stale(
    mock_is_stale: MagicMock, mock_set_suffix: MagicMock, make_changespec: Any
) -> None:
    """Test check_comment_zombies when no comments are stale."""
    mock_is_stale.return_value = False

    comments = [
        CommentEntry(
            reviewer="critique",
            file_path="/path/to/comments.json",
            suffix="241225_120000",
        )
    ]
    cs = make_changespec.create(comments=comments)

    result = check_comment_zombies(cs)

    assert result == []
    mock_is_stale.assert_called_once()
    mock_set_suffix.assert_not_called()


@patch("ace.scheduler.comments_handler.set_comment_suffix")
@patch("ace.scheduler.comments_handler.is_comments_suffix_stale")
def test_check_comment_zombies_one_stale(
    mock_is_stale: MagicMock, mock_set_suffix: MagicMock, make_changespec: Any
) -> None:
    """Test check_comment_zombies marks stale comment as ZOMBIE."""
    mock_is_stale.return_value = True

    comments = [
        CommentEntry(
            reviewer="critique",
            file_path="/path/to/comments.json",
            suffix="241225_120000",
        )
    ]
    cs = make_changespec.create(comments=comments)

    result = check_comment_zombies(cs)

    assert len(result) == 1
    assert "critique" in result[0]
    assert "ZOMBIE" in result[0]
    mock_set_suffix.assert_called_once_with(
        cs.file_path,
        cs.name,
        "critique",
        "ZOMBIE",
        comments,
    )


@patch("ace.scheduler.comments_handler.set_comment_suffix")
@patch("ace.scheduler.comments_handler.is_comments_suffix_stale")
def test_check_comment_zombies_multiple_mixed(
    mock_is_stale: MagicMock, mock_set_suffix: MagicMock, make_changespec: Any
) -> None:
    """Test check_comment_zombies with mix of stale and fresh comments."""
    # First call returns True (stale), second returns False (fresh)
    mock_is_stale.side_effect = [True, False]

    comments = [
        CommentEntry(
            reviewer="critique", file_path="/path/to/c1.json", suffix="241225_100000"
        ),
        CommentEntry(
            reviewer="critique:me", file_path="/path/to/c2.json", suffix="241225_120000"
        ),
    ]
    cs = make_changespec.create(comments=comments)

    result = check_comment_zombies(cs)

    assert len(result) == 1
    assert "critique" in result[0]
    mock_set_suffix.assert_called_once()


@patch("ace.scheduler.comments_handler.set_comment_suffix")
@patch("ace.scheduler.comments_handler.is_comments_suffix_stale")
def test_check_comment_zombies_all_stale(
    mock_is_stale: MagicMock, mock_set_suffix: MagicMock, make_changespec: Any
) -> None:
    """Test check_comment_zombies when all comments are stale."""
    mock_is_stale.return_value = True

    comments = [
        CommentEntry(
            reviewer="critique", file_path="/path/to/c1.json", suffix="241225_100000"
        ),
        CommentEntry(
            reviewer="critique:me", file_path="/path/to/c2.json", suffix="241225_100000"
        ),
    ]
    cs = make_changespec.create(comments=comments)

    result = check_comment_zombies(cs)

    assert len(result) == 2
    assert mock_set_suffix.call_count == 2


@patch("ace.scheduler.comments_handler.set_comment_suffix")
@patch("ace.scheduler.comments_handler.is_comments_suffix_stale")
def test_check_comment_zombies_custom_timeout(
    mock_is_stale: MagicMock, mock_set_suffix: MagicMock, make_changespec: Any
) -> None:
    """Test check_comment_zombies passes custom timeout to is_comments_suffix_stale."""
    mock_is_stale.return_value = False

    comments = [
        CommentEntry(
            reviewer="critique", file_path="/path/to/c.json", suffix="241225_120000"
        )
    ]
    cs = make_changespec.create(comments=comments)

    custom_timeout = 3600  # 1 hour
    check_comment_zombies(cs, zombie_timeout_seconds=custom_timeout)

    # Verify custom timeout was passed
    mock_is_stale.assert_called_once_with("241225_120000", custom_timeout)

"""Tests for work_projects_workflow module."""

import os
from unittest.mock import patch

from work_projects_workflow.workflow_nodes import (
    _extract_bug_id,
    _extract_cl_id,
    _is_in_tmux,
)


def test_extract_bug_id_plain_format() -> None:
    """Test extracting bug ID from plain format."""
    assert _extract_bug_id("12345") == "12345"


def test_extract_bug_id_http_url_format() -> None:
    """Test extracting bug ID from http URL format."""
    assert _extract_bug_id("http://b/12345") == "12345"


def test_extract_bug_id_https_url_format() -> None:
    """Test extracting bug ID from https URL format."""
    assert _extract_bug_id("https://b/12345") == "12345"


def test_extract_bug_id_with_whitespace() -> None:
    """Test extracting bug ID with surrounding whitespace."""
    assert _extract_bug_id("  12345  ") == "12345"


def test_extract_cl_id_plain_format() -> None:
    """Test extracting CL ID from plain format."""
    assert _extract_cl_id("12345") == "12345"


def test_extract_cl_id_legacy_format() -> None:
    """Test extracting CL ID from legacy format."""
    assert _extract_cl_id("cl/12345") == "12345"


def test_extract_cl_id_http_url_format() -> None:
    """Test extracting CL ID from http URL format."""
    assert _extract_cl_id("http://cl/12345") == "12345"


def test_extract_cl_id_https_url_format() -> None:
    """Test extracting CL ID from https URL format."""
    assert _extract_cl_id("https://cl/12345") == "12345"


def test_extract_cl_id_with_whitespace() -> None:
    """Test extracting CL ID with surrounding whitespace."""
    assert _extract_cl_id("  12345  ") == "12345"


def test_is_in_tmux_when_in_tmux() -> None:
    """Test _is_in_tmux returns True when TMUX env var is set."""
    with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
        assert _is_in_tmux() is True


def test_is_in_tmux_when_not_in_tmux() -> None:
    """Test _is_in_tmux returns False when TMUX env var is not set."""
    with patch.dict(os.environ, {}, clear=True):
        assert _is_in_tmux() is False


def test_is_in_tmux_when_empty_string() -> None:
    """Test _is_in_tmux returns True when TMUX env var is empty string."""
    with patch.dict(os.environ, {"TMUX": ""}):
        # Empty string still means env var is set, so should return True
        assert _is_in_tmux() is True

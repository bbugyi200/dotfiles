"""Tests for work_projects_workflow module."""

import os
from unittest.mock import patch

from work_projects_workflow import WorkProjectWorkflow
from work_projects_workflow.workflow_nodes import (
    _extract_bug_id,
    _extract_cl_id,
    _get_statuses_for_filters,
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


def test_get_statuses_for_filters_empty_list() -> None:
    """Test _get_statuses_for_filters returns empty set for empty list."""
    result = _get_statuses_for_filters([])
    assert result == set()


def test_get_statuses_for_filters_blocked() -> None:
    """Test _get_statuses_for_filters returns blocked statuses."""
    result = _get_statuses_for_filters(["blocked"])
    expected = {"Pre-Mailed", "Failed to Fix Tests", "Failed to Create CL"}
    assert result == expected


def test_get_statuses_for_filters_unblocked() -> None:
    """Test _get_statuses_for_filters returns unblocked statuses."""
    result = _get_statuses_for_filters(["unblocked"])
    expected = {"Not Started", "TDD CL Created"}
    assert result == expected


def test_get_statuses_for_filters_wip() -> None:
    """Test _get_statuses_for_filters returns wip statuses."""
    result = _get_statuses_for_filters(["wip"])
    expected = {"In Progress", "Fixing Tests"}
    assert result == expected


def test_get_statuses_for_filters_multiple() -> None:
    """Test _get_statuses_for_filters returns union of multiple filters."""
    result = _get_statuses_for_filters(["blocked", "unblocked"])
    expected = {
        "Pre-Mailed",
        "Failed to Fix Tests",
        "Failed to Create CL",
        "Not Started",
        "TDD CL Created",
    }
    assert result == expected


def test_get_statuses_for_filters_all() -> None:
    """Test _get_statuses_for_filters returns all statuses when all filters specified."""
    result = _get_statuses_for_filters(["blocked", "unblocked", "wip"])
    expected = {
        "Pre-Mailed",
        "Failed to Fix Tests",
        "Failed to Create CL",
        "Not Started",
        "TDD CL Created",
        "In Progress",
        "Fixing Tests",
    }
    assert result == expected


def test_get_statuses_for_filters_unknown_filter() -> None:
    """Test _get_statuses_for_filters ignores unknown filter names."""
    result = _get_statuses_for_filters(["unknown", "blocked"])
    expected = {"Pre-Mailed", "Failed to Fix Tests", "Failed to Create CL"}
    assert result == expected


def test_work_project_workflow_init_defaults() -> None:
    """Test WorkProjectWorkflow initializes with correct default values."""
    workflow = WorkProjectWorkflow()
    assert workflow.yolo is False
    assert workflow.max_changespecs is None
    assert workflow.include_filters == []


def test_work_project_workflow_init_with_params() -> None:
    """Test WorkProjectWorkflow initializes with provided parameters."""
    workflow = WorkProjectWorkflow(
        yolo=True, max_changespecs=5, include_filters=["blocked", "wip"]
    )
    assert workflow.yolo is True
    assert workflow.max_changespecs == 5
    assert workflow.include_filters == ["blocked", "wip"]


def test_work_project_workflow_init_none_filters() -> None:
    """Test WorkProjectWorkflow handles None include_filters."""
    workflow = WorkProjectWorkflow(include_filters=None)
    assert workflow.include_filters == []


def test_work_project_workflow_name() -> None:
    """Test WorkProjectWorkflow has correct name property."""
    workflow = WorkProjectWorkflow()
    assert workflow.name == "work"


def test_work_project_workflow_description() -> None:
    """Test WorkProjectWorkflow has correct description property."""
    workflow = WorkProjectWorkflow()
    assert workflow.description == "Process a ProjectSpec file to create the next CL"

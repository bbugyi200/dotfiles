"""Tests for work_projects_workflow module."""

import os
from unittest.mock import patch

from work_projects_workflow import WorkProjectWorkflow
from work_projects_workflow.workflow_nodes import (
    _count_eligible_changespecs,
    _extract_bug_id,
    _extract_cl_id,
    _format_changespec,
    _get_statuses_for_filters,
    _is_in_tmux,
    _parse_project_spec,
    _test_targets_to_command_args,
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


def test_count_eligible_changespecs_empty() -> None:
    """Test counting eligible ChangeSpecs with empty list."""
    changespecs: list[dict[str, str]] = []
    result = _count_eligible_changespecs(changespecs, [], [])
    assert result == 0


def test_count_eligible_changespecs_tdd_cl_created() -> None:
    """Test counting eligible ChangeSpecs with TDD CL Created status."""
    changespecs = [
        {"NAME": "cs1", "STATUS": "TDD CL Created"},
        {"NAME": "cs2", "STATUS": "Not Started", "PARENT": "None"},
        {"NAME": "cs3", "STATUS": "Pre-Mailed"},
    ]
    result = _count_eligible_changespecs(changespecs, [], [])
    assert result == 2  # cs1 (TDD CL Created) and cs2 (Not Started, no parent)


def test_count_eligible_changespecs_with_attempted() -> None:
    """Test counting eligible ChangeSpecs excludes attempted ones."""
    changespecs = [
        {"NAME": "cs1", "STATUS": "TDD CL Created"},
        {"NAME": "cs2", "STATUS": "Not Started", "PARENT": "None"},
        {"NAME": "cs3", "STATUS": "Not Started", "PARENT": "None"},
    ]
    result = _count_eligible_changespecs(changespecs, ["cs1", "cs2"], [])
    assert result == 1  # Only cs3 is not attempted


def test_count_eligible_changespecs_with_filters() -> None:
    """Test counting eligible ChangeSpecs with status filters."""
    changespecs = [
        {"NAME": "cs1", "STATUS": "TDD CL Created"},
        {"NAME": "cs2", "STATUS": "Not Started", "PARENT": "None"},
        {"NAME": "cs3", "STATUS": "Pre-Mailed"},
    ]
    result = _count_eligible_changespecs(changespecs, [], ["unblocked"])
    assert (
        result == 2
    )  # cs1 (TDD CL Created) and cs2 (Not Started) match unblocked filter


def test_count_eligible_changespecs_with_parent_dependency() -> None:
    """Test counting eligible ChangeSpecs respects parent dependencies."""
    changespecs = [
        {"NAME": "cs1", "STATUS": "Pre-Mailed"},
        {"NAME": "cs2", "STATUS": "Not Started", "PARENT": "cs1"},
        {
            "NAME": "cs3",
            "STATUS": "Not Started",
            "PARENT": "cs4",
        },  # Parent not completed
        {"NAME": "cs4", "STATUS": "In Progress"},
    ]
    result = _count_eligible_changespecs(changespecs, [], [])
    assert result == 1  # Only cs2 (parent cs1 is Pre-Mailed)


def test_count_eligible_changespecs_skips_no_name() -> None:
    """Test counting eligible ChangeSpecs skips entries without NAME."""
    changespecs = [
        {"STATUS": "TDD CL Created"},  # No NAME
        {"NAME": "cs2", "STATUS": "Not Started", "PARENT": "None"},
    ]
    result = _count_eligible_changespecs(changespecs, [], [])
    assert result == 1  # Only cs2


def test_format_changespec_basic() -> None:
    """Test formatting a ChangeSpec to text format."""
    cs = {
        "NAME": "test_changespec",
        "DESCRIPTION": "Test description\nLine 2",
        "PARENT": "None",
        "CL": "12345",
        "STATUS": "Not Started",
    }
    result = _format_changespec(cs)
    assert "NAME: test_changespec" in result
    assert "DESCRIPTION:" in result
    assert "  Test description" in result
    assert "  Line 2" in result
    assert "PARENT: None" in result
    assert "CL: 12345" in result
    assert "STATUS: Not Started" in result


def test_format_changespec_with_test_targets() -> None:
    """Test formatting a ChangeSpec with TEST TARGETS field."""
    cs = {
        "NAME": "test_cs",
        "DESCRIPTION": "Description",
        "PARENT": "parent_cs",
        "CL": "None",
        "TEST TARGETS": "//my/package:test",
        "STATUS": "TDD CL Created",
    }
    result = _format_changespec(cs)
    assert "NAME: test_cs" in result
    assert "PARENT: parent_cs" in result
    assert "TEST TARGETS: //my/package:test" in result
    assert "STATUS: TDD CL Created" in result


def test_parse_multiline_test_targets() -> None:
    """Test parsing multi-line TEST TARGETS format."""
    spec = """NAME: Test Project
DESCRIPTION:
  Test description

TEST TARGETS:
  //my/package:test1
  //other/package:test2
  //third:integration_test

STATUS: Not Started
"""
    _, changespecs = _parse_project_spec(spec)
    assert len(changespecs) == 1
    cs = changespecs[0]
    assert (
        cs["TEST TARGETS"]
        == "//my/package:test1\n//other/package:test2\n//third:integration_test"
    )


def test_parse_singleline_test_targets_backwards_compat() -> None:
    """Test parsing single-line TEST TARGETS (backwards compatibility)."""
    spec = """NAME: Test Project
DESCRIPTION:
  Test description

TEST TARGETS: //my/package:test1 //other/package:test2
STATUS: Not Started
"""
    _, changespecs = _parse_project_spec(spec)
    assert len(changespecs) == 1
    cs = changespecs[0]
    assert cs["TEST TARGETS"] == "//my/package:test1 //other/package:test2"


def test_parse_test_targets_none() -> None:
    """Test parsing TEST TARGETS with None value."""
    spec = """NAME: Test Project
DESCRIPTION:
  Test description

TEST TARGETS: None
STATUS: Not Started
"""
    _, changespecs = _parse_project_spec(spec)
    assert len(changespecs) == 1
    cs = changespecs[0]
    assert cs["TEST TARGETS"] == "None"


def test_parse_test_targets_blank_line_terminates() -> None:
    """Test that blank lines terminate TEST TARGETS field."""
    spec = """NAME: Test Project
DESCRIPTION:
  Test description

TEST TARGETS:
  //my/package:test1

  //other/package:test2
STATUS: Not Started
"""
    _, changespecs = _parse_project_spec(spec)
    assert len(changespecs) == 1
    cs = changespecs[0]
    # Should only have test1, blank line terminates the field
    assert cs["TEST TARGETS"] == "//my/package:test1"
    # Should not contain blank lines
    assert "\n\n" not in cs.get("TEST TARGETS", "")


def test_format_multiline_test_targets() -> None:
    """Test formatting multi-line TEST TARGETS."""
    cs = {
        "NAME": "Test",
        "DESCRIPTION": "Description",
        "PARENT": "None",
        "CL": "None",
        "TEST TARGETS": "//my/package:test1\n//other/package:test2",
        "STATUS": "Not Started",
    }
    result = _format_changespec(cs)
    assert "TEST TARGETS:" in result
    assert "  //my/package:test1" in result
    assert "  //other/package:test2" in result


def test_format_singleline_test_targets() -> None:
    """Test formatting single-line TEST TARGETS (backwards compatibility)."""
    cs = {
        "NAME": "Test",
        "DESCRIPTION": "Description",
        "PARENT": "None",
        "CL": "None",
        "TEST TARGETS": "//my/package:test1",
        "STATUS": "Not Started",
    }
    result = _format_changespec(cs)
    assert "TEST TARGETS: //my/package:test1" in result


def test_format_test_targets_none() -> None:
    """Test formatting TEST TARGETS with None value."""
    cs = {
        "NAME": "Test",
        "DESCRIPTION": "Description",
        "PARENT": "None",
        "CL": "None",
        "TEST TARGETS": "None",
        "STATUS": "Not Started",
    }
    result = _format_changespec(cs)
    assert "TEST TARGETS: None" in result


def test_test_targets_to_command_args_multiline() -> None:
    """Test converting multi-line test targets to command args."""
    multi = "//my/package:test1\n//other/package:test2"
    assert (
        _test_targets_to_command_args(multi)
        == "//my/package:test1 //other/package:test2"
    )


def test_test_targets_to_command_args_singleline() -> None:
    """Test converting single-line test targets to command args (unchanged)."""
    single = "//my/package:test1 //other:test2"
    assert _test_targets_to_command_args(single) == single


def test_test_targets_to_command_args_none() -> None:
    """Test converting None test targets to command args (unchanged)."""
    assert _test_targets_to_command_args("None") == "None"


def test_test_targets_to_command_args_empty() -> None:
    """Test converting empty test targets to command args (unchanged)."""
    assert _test_targets_to_command_args("") == ""


def test_count_eligible_changespecs_blocked_filter_includes_premailed() -> None:
    """Test that blocked filter includes Pre-Mailed ChangeSpecs."""
    changespecs = [
        {"NAME": "cs1", "STATUS": "Pre-Mailed"},
        {"NAME": "cs2", "STATUS": "Failed to Fix Tests"},
        {"NAME": "cs3", "STATUS": "Failed to Create CL"},
        {"NAME": "cs4", "STATUS": "Not Started", "PARENT": "None"},
    ]
    result = _count_eligible_changespecs(changespecs, [], ["blocked"])
    assert (
        result == 3
    )  # cs1 (Pre-Mailed), cs2 (Failed to Fix Tests), cs3 (Failed to Create CL)

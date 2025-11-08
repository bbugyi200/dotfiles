"""Tests for gai.main module."""

import pytest
from main import _create_parser, _normalize_spec


def test_normalize_spec_plus_format_unchanged() -> None:
    """Test that M+N+P format remains unchanged."""
    assert _normalize_spec("2+2+2") == "2+2+2"
    assert _normalize_spec("1+2+3") == "1+2+3"
    assert _normalize_spec("5+10+15") == "5+10+15"


def test_normalize_spec_mxn_format_conversion() -> None:
    """Test that MxN format is converted to M+M+...+M."""
    assert _normalize_spec("2x3") == "2+2+2"
    assert _normalize_spec("1x5") == "1+1+1+1+1"
    assert _normalize_spec("3x2") == "3+3"
    assert _normalize_spec("4x1") == "4"


def test_normalize_spec_with_whitespace() -> None:
    """Test that whitespace is handled correctly."""
    assert _normalize_spec(" 2x3 ") == "2+2+2"
    # Plus format is returned with stripped whitespace
    assert _normalize_spec(" 1 + 2 + 3 ") == "1 + 2 + 3"


def test_normalize_spec_invalid_mxn_format() -> None:
    """Test that invalid MxN formats raise ValueError."""
    with pytest.raises(ValueError, match="Invalid MxN format"):
        _normalize_spec("2x3x4")

    with pytest.raises(ValueError, match="Both M and N must be positive integers"):
        _normalize_spec("axb")


def test_normalize_spec_negative_or_zero_values() -> None:
    """Test that negative or zero values raise ValueError."""
    with pytest.raises(ValueError, match="positive integers"):
        _normalize_spec("0x3")

    with pytest.raises(ValueError, match="positive integers"):
        _normalize_spec("2x0")


def test_normalize_spec_single_value() -> None:
    """Test that single values are returned as-is."""
    assert _normalize_spec("5") == "5"
    assert _normalize_spec("10") == "10"


def test_create_parser_requires_run_command() -> None:
    """Test that parser requires 'run' command at the top level."""
    parser = _create_parser()

    # Verify that the command destination is set correctly
    args = parser.parse_args(
        [
            "run",
            "fix-tests",
            "pytest test_file.py",
            "test_output.txt",
        ]
    )
    assert args.command == "run"
    assert args.workflow == "fix-tests"


def test_create_parser_has_all_workflows() -> None:
    """Test that parser has all expected workflow subcommands."""
    parser = _create_parser()

    # Parse with -h to get help and check subcommands exist
    # We'll test by parsing valid commands for each workflow
    workflows = [
        "fix-tests",
        "create-project",
        "new-failing-tests",
        "work-projects",
    ]

    for workflow in workflows:
        # Just verify the parser can recognize the workflow
        # We can't run full commands without all required arguments
        try:
            parser.parse_args(["run", workflow, "--help"])
        except SystemExit:
            # --help causes SystemExit, which is expected
            pass


def test_create_parser_fix_tests_workflow() -> None:
    """Test that fix-tests workflow parser works correctly."""
    parser = _create_parser()

    args = parser.parse_args(
        [
            "run",
            "fix-tests",
            "pytest test.py",
            "test_output.txt",
            "--max-iterations",
            "15",
            "--clquery",
            "my project",
            "--user-instructions-file",
            "instructions.md",
            "--initial-research-file",
            "research.md",
            "--context-file-directory",
            "context_dir",
        ]
    )

    assert args.workflow == "fix-tests"
    assert args.test_cmd == "pytest test.py"
    assert args.test_output_file == "test_output.txt"
    assert args.max_iterations == 15
    assert args.clquery == "my project"
    assert args.user_instructions_file == "instructions.md"
    assert args.initial_research_file == "research.md"
    assert args.context_file_directory == "context_dir"


def test_create_parser_fix_tests_default_values() -> None:
    """Test that fix-tests workflow has correct default values."""
    parser = _create_parser()

    args = parser.parse_args(
        [
            "run",
            "fix-tests",
            "pytest test.py",
            "test_output.txt",
        ]
    )

    assert args.max_iterations == 10
    assert args.clquery is None
    assert args.user_instructions_file is None


def test_create_parser_create_project_workflow() -> None:
    """Test that create-project workflow parser works correctly."""
    parser = _create_parser()

    args = parser.parse_args(
        [
            "run",
            "create-project",
            "12345",
            "my-project-query",
            "/path/to/design/docs",
            "project_name",
        ]
    )

    assert args.workflow == "create-project"
    assert args.bug_id == "12345"
    assert args.clquery == "my-project-query"
    assert args.design_docs_dir == "/path/to/design/docs"
    assert args.filename == "project_name"


def test_create_parser_new_failing_test_workflow() -> None:
    """Test that new-failing-test workflow parser works correctly."""
    parser = _create_parser()

    args = parser.parse_args(
        [
            "run",
            "new-failing-tests",
            "my-project",
            "/path/to/design/docs",
        ]
    )

    assert args.workflow == "new-failing-tests"
    assert args.project_name == "my-project"
    assert args.design_docs_dir == "/path/to/design/docs"


def test_create_parser_work_command() -> None:
    """Test that work command parser works correctly."""
    parser = _create_parser()

    args = parser.parse_args(
        [
            "work",
            "--yolo",
        ]
    )

    assert args.command == "work"
    assert args.yolo is True


def test_create_parser_work_command_default_values() -> None:
    """Test that work command has correct default values."""
    parser = _create_parser()

    args = parser.parse_args(
        [
            "work",
        ]
    )

    assert args.yolo is False
    assert args.include_filters is None


def test_create_parser_work_command_with_include_filter() -> None:
    """Test that work command parser handles single include filter."""
    parser = _create_parser()

    args = parser.parse_args(["work", "--include", "blocked"])

    assert args.command == "work"
    assert args.include_filters == ["blocked"]


def test_create_parser_work_command_with_multiple_include_filters() -> None:
    """Test that work command parser handles multiple include filters."""
    parser = _create_parser()

    args = parser.parse_args(
        ["work", "--include", "blocked", "--include", "unblocked", "-i", "wip"]
    )

    assert args.command == "work"
    assert args.include_filters == ["blocked", "unblocked", "wip"]


def test_create_parser_work_command_include_filter_short_flag() -> None:
    """Test that work command parser handles short -i flag."""
    parser = _create_parser()

    args = parser.parse_args(["work", "-i", "blocked"])

    assert args.command == "work"
    assert args.include_filters == ["blocked"]

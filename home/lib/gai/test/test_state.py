"""Tests for gai.fix_tests_workflow.state module."""

from typing import cast

from fix_tests_workflow.state import (
    FixTestsState,
    extract_file_modifications_from_response,
    get_latest_planner_response,
)
from langchain_core.messages import AIMessage, HumanMessage


def test_get_latest_planner_response_with_valid_response() -> None:
    """Test extracting planner response from state messages."""
    state = cast(
        FixTestsState,
        {
            "messages": [
                HumanMessage(content="Initial message"),
                AIMessage(
                    content="# Analysis and Planning\n\nThis is a planner response."
                ),
                AIMessage(content="Some other message"),
            ]
        },
    )

    result = get_latest_planner_response(state)
    assert "# Analysis and Planning" in result
    assert "This is a planner response." in result


def test_get_latest_planner_response_with_file_modifications() -> None:
    """Test extracting planner response that contains File Modifications section."""
    state = cast(
        FixTestsState,
        {
            "messages": [
                AIMessage(
                    content="# File Modifications\n\nModify file1.py\nModify file2.py"
                ),
            ]
        },
    )

    result = get_latest_planner_response(state)
    assert "# File Modifications" in result
    assert "Modify file1.py" in result


def test_get_latest_planner_response_with_no_planner_response() -> None:
    """Test that empty string is returned when no planner response is found."""
    state = cast(
        FixTestsState,
        {
            "messages": [
                HumanMessage(content="Just a user message"),
                AIMessage(content="Regular AI response without planner markers"),
            ]
        },
    )

    result = get_latest_planner_response(state)
    assert result == ""


def test_get_latest_planner_response_with_empty_messages() -> None:
    """Test that empty string is returned when there are no messages."""
    state: FixTestsState = cast(FixTestsState, {"messages": []})

    result = get_latest_planner_response(state)
    assert result == ""


def test_get_latest_planner_response_returns_most_recent() -> None:
    """Test that the most recent planner response is returned."""
    state = cast(
        FixTestsState,
        {
            "messages": [
                AIMessage(content="# Analysis and Planning\n\nFirst planner response"),
                AIMessage(content="Some other message"),
                AIMessage(content="# Analysis and Planning\n\nSecond planner response"),
            ]
        },
    )

    result = get_latest_planner_response(state)
    assert "Second planner response" in result
    assert "First planner response" not in result


def test_extract_file_modifications_from_response_with_valid_section() -> None:
    """Test extracting File Modifications section from response."""
    response = """# Analysis and Planning

Some analysis here

# File Modifications

file1.py: Update function foo()
file2.py: Add new class Bar

# Other Section

Some other content"""

    result = extract_file_modifications_from_response(response)
    assert "file1.py: Update function foo()" in result
    assert "file2.py: Add new class Bar" in result
    assert "# Other Section" not in result
    assert "Some other content" not in result


def test_extract_file_modifications_from_response_no_section() -> None:
    """Test that empty string is returned when no File Modifications section."""
    response = """# Analysis and Planning

Some analysis here

# Other Section

Some content"""

    result = extract_file_modifications_from_response(response)
    assert result == ""


def test_extract_file_modifications_from_response_empty_section() -> None:
    """Test that empty string is returned when File Modifications section is empty."""
    response = """# File Modifications

# Other Section"""

    result = extract_file_modifications_from_response(response)
    assert result == ""


def test_extract_file_modifications_from_response_with_empty_string() -> None:
    """Test that empty string input returns empty string."""
    result = extract_file_modifications_from_response("")
    assert result == ""


def test_extract_file_modifications_from_response_at_end() -> None:
    """Test extracting File Modifications section when it's at the end."""
    response = """# Analysis and Planning

Some analysis

# File Modifications

file1.py: Update function
file2.py: Add class"""

    result = extract_file_modifications_from_response(response)
    assert "file1.py: Update function" in result
    assert "file2.py: Add class" in result


def test_extract_file_modifications_from_response_strips_whitespace() -> None:
    """Test that result is stripped of leading/trailing whitespace."""
    response = """# File Modifications

   file1.py: Update function

   file2.py: Add class
"""

    result = extract_file_modifications_from_response(response)
    # Result should be stripped of leading/trailing whitespace but preserve internal whitespace
    assert "file1.py: Update function" in result
    assert "file2.py: Add class" in result

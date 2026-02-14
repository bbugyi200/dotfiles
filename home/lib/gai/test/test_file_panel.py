"""Tests for file panel features and workflow output_types extraction."""

import tempfile
from typing import Any
from unittest.mock import MagicMock

from xprompt.models import OutputSpec
from xprompt.workflow_executor import WorkflowExecutor

# --- _get_output_types tests ---


def _make_executor_with_steps(
    steps: list[Any],
) -> WorkflowExecutor:
    """Create a WorkflowExecutor with given steps for testing."""
    workflow = MagicMock()
    workflow.steps = steps
    workflow.inputs = []
    workflow.name = "test"
    workflow.appears_as_agent.return_value = False

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = WorkflowExecutor(
            workflow=workflow,
            args={},
            artifacts_dir=tmpdir,
        )
    return executor


def test_get_output_types_returns_type_mapping() -> None:
    """Test that _get_output_types returns correct type mapping from OutputSpec."""
    output_spec = OutputSpec(
        type="json_schema",
        schema={
            "properties": {
                "success": {"type": "bool"},
                "cl_url": {"type": "line"},
                "diff_path": {"type": "path"},
                "error": {"type": "text"},
            }
        },
    )
    step = MagicMock()
    step.name = "create_cl"
    step.output = output_spec
    step.hidden = False
    step.condition = None
    step.for_loop = None
    step.repeat_config = None
    step.while_config = None
    step.parallel_config = None

    executor = _make_executor_with_steps([step])
    result = executor._get_output_types(0)

    assert result == {
        "success": "bool",
        "cl_url": "line",
        "diff_path": "path",
        "error": "text",
    }


def test_get_output_types_returns_none_when_no_output() -> None:
    """Test that _get_output_types returns None when step has no output spec."""
    step = MagicMock()
    step.name = "check"
    step.output = None
    step.hidden = False
    step.condition = None
    step.for_loop = None
    step.repeat_config = None
    step.while_config = None
    step.parallel_config = None

    executor = _make_executor_with_steps([step])
    result = executor._get_output_types(0)

    assert result is None


def test_get_output_types_returns_none_when_no_properties() -> None:
    """Test that _get_output_types returns None when schema has no properties."""
    output_spec = OutputSpec(type="json_schema", schema={"type": "array"})
    step = MagicMock()
    step.name = "check"
    step.output = output_spec
    step.hidden = False
    step.condition = None
    step.for_loop = None
    step.repeat_config = None
    step.while_config = None
    step.parallel_config = None

    executor = _make_executor_with_steps([step])
    result = executor._get_output_types(0)

    assert result is None


# --- Path extraction from workflow state data tests ---


def _extract_diff_path_from_steps(steps_data: list[dict[str, Any]]) -> str | None:
    """Extract diff_path from workflow state steps data.

    This mirrors the logic in load_workflow_states().
    """
    diff_path = None
    for step_data in steps_data:
        output_types = step_data.get("output_types") or {}
        step_output = step_data.get("output")
        if output_types and isinstance(step_output, dict):
            for field_name, field_type in output_types.items():
                if field_type == "path":
                    path_value = step_output.get(field_name)
                    if path_value:
                        diff_path = str(path_value)
    return diff_path


def test_extract_diff_path_finds_path_typed_output() -> None:
    """Test that path-typed output fields are correctly extracted."""
    steps = [
        {
            "name": "create_cl",
            "status": "completed",
            "output": {
                "success": True,
                "cl_url": "http://cl/123",
                "diff_path": "/tmp/test.diff",
                "error": "",
            },
            "output_types": {
                "success": "bool",
                "cl_url": "line",
                "diff_path": "path",
                "error": "text",
            },
        }
    ]
    assert _extract_diff_path_from_steps(steps) == "/tmp/test.diff"


def test_extract_diff_path_returns_none_when_no_path_type() -> None:
    """Test that None is returned when no path-typed fields exist."""
    steps = [
        {
            "name": "check",
            "status": "completed",
            "output": {"has_changes": True},
            "output_types": {"has_changes": "bool"},
        }
    ]
    assert _extract_diff_path_from_steps(steps) is None


def test_extract_diff_path_returns_none_when_empty_path() -> None:
    """Test that empty path values are ignored."""
    steps = [
        {
            "name": "create_cl",
            "status": "completed",
            "output": {"diff_path": "", "error": "something failed"},
            "output_types": {"diff_path": "path", "error": "text"},
        }
    ]
    assert _extract_diff_path_from_steps(steps) is None


def test_extract_diff_path_returns_none_when_no_output_types() -> None:
    """Test backward compat: steps without output_types are skipped."""
    steps = [
        {
            "name": "create_cl",
            "status": "completed",
            "output": {"diff_path": "/tmp/test.diff"},
        }
    ]
    assert _extract_diff_path_from_steps(steps) is None


def test_extract_diff_path_uses_last_path() -> None:
    """Test that the last path-typed output wins when multiple steps have paths."""
    steps = [
        {
            "name": "save_response",
            "status": "completed",
            "output": {"data_file": "/tmp/data.json"},
            "output_types": {"data_file": "path"},
        },
        {
            "name": "create_cl",
            "status": "completed",
            "output": {"diff_path": "/tmp/final.diff"},
            "output_types": {"diff_path": "path"},
        },
    ]
    assert _extract_diff_path_from_steps(steps) == "/tmp/final.diff"


# --- display_static_file tests ---


def test_display_static_file_reads_and_renders(tmp_path: Any) -> None:
    """Test that display_static_file reads file content and posts visibility message."""
    diff_file = tmp_path / "test.diff"
    diff_file.write_text("--- a/foo\n+++ b/foo\n@@ -1 +1 @@\n-old\n+new\n")

    # Create a mock panel that tracks method calls
    panel = MagicMock()
    panel.post_message = MagicMock()
    panel._has_displayed_content = False

    # Import and call the method directly using the unbound function
    from ace.tui.widgets.file_panel import _EXTENSION_TO_LEXER, AgentFilePanel

    # Verify the lexer mapping includes .diff
    assert _EXTENSION_TO_LEXER[".diff"] == "diff"

    # Test the method logic by calling it on the mock
    AgentFilePanel.display_static_file(panel, str(diff_file))

    # Verify update was called with a Group containing the path header and syntax
    assert panel.update.called
    from rich.console import Group

    group = panel.update.call_args[0][0]
    assert isinstance(group, Group)
    renderables = list(group._renderables)
    assert len(renderables) == 3
    # First element is the path header
    from rich.text import Text

    assert isinstance(renderables[0], Text)
    assert str(renderables[0]) == str(diff_file)
    # Second element is an empty separator line
    assert isinstance(renderables[1], Text)
    assert str(renderables[1]) == ""
    # Third element is the Syntax content
    from rich.syntax import Syntax

    assert isinstance(renderables[2], Syntax)
    # Verify visibility message was posted
    panel.post_message.assert_called()


def test_display_static_file_handles_missing_file(tmp_path: Any) -> None:
    """Test that display_static_file handles missing files gracefully."""
    panel = MagicMock()
    panel.post_message = MagicMock()

    from ace.tui.widgets.file_panel import AgentFilePanel

    AgentFilePanel.display_static_file(panel, str(tmp_path / "nonexistent.diff"))

    # Should post has_file=False
    panel.post_message.assert_called()
    call_args = panel.post_message.call_args[0][0]
    assert call_args.has_file is False


def test_display_static_file_handles_empty_file(tmp_path: Any) -> None:
    """Test that display_static_file handles empty files gracefully."""
    empty_file = tmp_path / "empty.diff"
    empty_file.write_text("")

    panel = MagicMock()
    panel.post_message = MagicMock()

    from ace.tui.widgets.file_panel import AgentFilePanel

    AgentFilePanel.display_static_file(panel, str(empty_file))

    # Should post has_file=False
    call_args = panel.post_message.call_args[0][0]
    assert call_args.has_file is False


def test_extension_to_lexer_mapping() -> None:
    """Test that the extension-to-lexer mapping includes common types."""
    from ace.tui.widgets.file_panel import _EXTENSION_TO_LEXER

    assert _EXTENSION_TO_LEXER[".diff"] == "diff"
    assert _EXTENSION_TO_LEXER[".py"] == "python"
    assert _EXTENSION_TO_LEXER[".json"] == "json"
    assert _EXTENSION_TO_LEXER[".yml"] == "yaml"
    assert _EXTENSION_TO_LEXER[".sh"] == "bash"

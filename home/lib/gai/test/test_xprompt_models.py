"""Tests for the xprompt.models module."""

from pathlib import Path

import pytest
from xprompt.models import (
    UNSET,
    InputArg,
    InputType,
    XPrompt,
    XPromptValidationError,
    create_adhoc_workflow,
    xprompt_to_workflow,
)

# Tests for InputType enum


def test_input_type_values() -> None:
    """Test that InputType enum has expected values."""
    assert InputType.WORD.value == "word"
    assert InputType.LINE.value == "line"
    assert InputType.TEXT.value == "text"
    assert InputType.PATH.value == "path"
    assert InputType.INT.value == "int"
    assert InputType.BOOL.value == "bool"
    assert InputType.FLOAT.value == "float"


# Tests for InputArg.validate_and_convert


def test_input_arg_word_validation() -> None:
    """Test that word type validates no whitespace."""
    arg = InputArg(name="test", type=InputType.WORD)
    assert arg.validate_and_convert("hello") == "hello"
    assert arg.validate_and_convert("123") == "123"
    assert arg.validate_and_convert("") == ""
    assert arg.validate_and_convert("hello-world_123") == "hello-world_123"


def test_input_arg_word_rejects_whitespace() -> None:
    """Test that word type rejects values with whitespace."""
    arg = InputArg(name="test", type=InputType.WORD)
    with pytest.raises(XPromptValidationError, match="expects word"):
        arg.validate_and_convert("hello world")
    with pytest.raises(XPromptValidationError, match="expects word"):
        arg.validate_and_convert("hello\tworld")
    with pytest.raises(XPromptValidationError, match="expects word"):
        arg.validate_and_convert("hello\nworld")


def test_input_arg_line_validation() -> None:
    """Test that line type allows spaces but not newlines."""
    arg = InputArg(name="test", type=InputType.LINE)
    assert arg.validate_and_convert("hello world") == "hello world"
    assert arg.validate_and_convert("hello\tworld") == "hello\tworld"
    assert arg.validate_and_convert("") == ""


def test_input_arg_line_rejects_newlines() -> None:
    """Test that line type rejects values with newlines."""
    arg = InputArg(name="test", type=InputType.LINE)
    with pytest.raises(XPromptValidationError, match="expects line"):
        arg.validate_and_convert("hello\nworld")
    with pytest.raises(XPromptValidationError, match="expects line"):
        arg.validate_and_convert("line1\nline2\nline3")


def test_input_arg_text_passthrough() -> None:
    """Test that text type passes through any content unchanged."""
    arg = InputArg(name="test", type=InputType.TEXT)
    assert arg.validate_and_convert("hello") == "hello"
    assert arg.validate_and_convert("hello world") == "hello world"
    assert arg.validate_and_convert("line1\nline2") == "line1\nline2"
    assert arg.validate_and_convert("") == ""


def test_input_arg_path_validation(tmp_path: Path) -> None:
    """Test that path type validates file exists."""
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    arg = InputArg(name="test", type=InputType.PATH)
    result = arg.validate_and_convert(str(test_file))
    assert result == str(test_file)


def test_input_arg_path_rejects_whitespace() -> None:
    """Test that path type rejects values with whitespace."""
    arg = InputArg(name="test", type=InputType.PATH)
    with pytest.raises(XPromptValidationError, match="expects path"):
        arg.validate_and_convert("/path/with spaces/file.txt")


def test_input_arg_path_rejects_nonexistent() -> None:
    """Test that path type rejects non-existent paths."""
    arg = InputArg(name="test", type=InputType.PATH)
    with pytest.raises(XPromptValidationError, match="does not exist"):
        arg.validate_and_convert("/nonexistent/path/that/does/not/exist.txt")


def test_input_arg_int_conversion() -> None:
    """Test int type conversion."""
    arg = InputArg(name="count", type=InputType.INT)
    assert arg.validate_and_convert("42") == 42
    assert arg.validate_and_convert("-10") == -10
    assert arg.validate_and_convert("0") == 0


def test_input_arg_int_invalid_raises_error() -> None:
    """Test that invalid int raises error."""
    arg = InputArg(name="count", type=InputType.INT)
    with pytest.raises(XPromptValidationError, match="expects int"):
        arg.validate_and_convert("not_a_number")
    with pytest.raises(XPromptValidationError, match="expects int"):
        arg.validate_and_convert("3.14")


def test_input_arg_float_conversion() -> None:
    """Test float type conversion."""
    arg = InputArg(name="ratio", type=InputType.FLOAT)
    assert arg.validate_and_convert("3.14") == 3.14
    assert arg.validate_and_convert("-2.5") == -2.5
    assert arg.validate_and_convert("42") == 42.0


def test_input_arg_float_invalid_raises_error() -> None:
    """Test that invalid float raises error."""
    arg = InputArg(name="ratio", type=InputType.FLOAT)
    with pytest.raises(XPromptValidationError, match="expects float"):
        arg.validate_and_convert("not_a_float")


def test_input_arg_bool_conversion_true_values() -> None:
    """Test bool type converts truthy string values to True."""
    arg = InputArg(name="enabled", type=InputType.BOOL)
    for value in ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]:
        assert arg.validate_and_convert(value) is True


def test_input_arg_bool_conversion_false_values() -> None:
    """Test bool type converts falsy string values to False."""
    arg = InputArg(name="enabled", type=InputType.BOOL)
    for value in ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF"]:
        assert arg.validate_and_convert(value) is False


def test_input_arg_bool_invalid_raises_error() -> None:
    """Test that invalid bool raises error."""
    arg = InputArg(name="enabled", type=InputType.BOOL)
    with pytest.raises(XPromptValidationError, match="expects bool"):
        arg.validate_and_convert("maybe")
    with pytest.raises(XPromptValidationError, match="expects bool"):
        arg.validate_and_convert("")


def test_input_arg_default_type_is_line() -> None:
    """Test that default type is LINE."""
    arg = InputArg(name="test")
    assert arg.type == InputType.LINE


def test_input_arg_default_is_unset() -> None:
    """Test that default value is UNSET when not specified."""
    arg = InputArg(name="test")
    assert arg.default is UNSET


def test_input_arg_with_default_value() -> None:
    """Test InputArg with a default value."""
    arg = InputArg(name="count", type=InputType.INT, default=10)
    assert arg.default == 10


# Tests for XPrompt


def test_xprompt_basic_construction() -> None:
    """Test basic XPrompt construction."""
    xp = XPrompt(name="test", content="Hello world")
    assert xp.name == "test"
    assert xp.content == "Hello world"
    assert xp.inputs == []
    assert xp.source_path is None


def test_xprompt_with_inputs() -> None:
    """Test XPrompt with input definitions."""
    inputs = [
        InputArg(name="name", type=InputType.LINE),
        InputArg(name="count", type=InputType.INT, default=5),
    ]
    xp = XPrompt(name="test", content="Hello {{ name }}", inputs=inputs)
    assert len(xp.inputs) == 2
    assert xp.inputs[0].name == "name"
    assert xp.inputs[1].name == "count"
    assert xp.inputs[1].default == 5


def test_xprompt_with_source_path() -> None:
    """Test XPrompt with source path."""
    xp = XPrompt(name="test", content="content", source_path="/path/to/file.md")
    assert xp.source_path == "/path/to/file.md"


def test_xprompt_get_input_by_name_found() -> None:
    """Test getting input by name when it exists."""
    inputs = [
        InputArg(name="alpha", type=InputType.LINE),
        InputArg(name="beta", type=InputType.INT),
    ]
    xp = XPrompt(name="test", content="", inputs=inputs)

    result = xp.get_input_by_name("beta")
    assert result is not None
    assert result.name == "beta"
    assert result.type == InputType.INT


def test_xprompt_get_input_by_name_not_found() -> None:
    """Test getting input by name when it doesn't exist."""
    inputs = [InputArg(name="alpha", type=InputType.LINE)]
    xp = XPrompt(name="test", content="", inputs=inputs)

    result = xp.get_input_by_name("gamma")
    assert result is None


def test_xprompt_get_input_by_name_empty_inputs() -> None:
    """Test getting input by name with no inputs defined."""
    xp = XPrompt(name="test", content="")
    assert xp.get_input_by_name("anything") is None


def test_xprompt_get_input_by_position_found() -> None:
    """Test getting input by position when it exists."""
    inputs = [
        InputArg(name="first", type=InputType.LINE),
        InputArg(name="second", type=InputType.INT),
    ]
    xp = XPrompt(name="test", content="", inputs=inputs)

    result = xp.get_input_by_position(0)
    assert result is not None
    assert result.name == "first"

    result = xp.get_input_by_position(1)
    assert result is not None
    assert result.name == "second"


def test_xprompt_get_input_by_position_out_of_range() -> None:
    """Test getting input by position when out of range."""
    inputs = [InputArg(name="first", type=InputType.LINE)]
    xp = XPrompt(name="test", content="", inputs=inputs)

    assert xp.get_input_by_position(-1) is None
    assert xp.get_input_by_position(1) is None
    assert xp.get_input_by_position(100) is None


def test_xprompt_get_input_by_position_empty_inputs() -> None:
    """Test getting input by position with no inputs defined."""
    xp = XPrompt(name="test", content="")
    assert xp.get_input_by_position(0) is None


# Tests for xprompt_to_workflow


def test_xprompt_to_workflow_basic() -> None:
    """Test basic xprompt to workflow conversion."""
    xp = XPrompt(name="explain", content="Explain this code: {{ code }}")
    workflow = xprompt_to_workflow(xp)

    assert workflow.name == "explain"
    assert len(workflow.steps) == 1
    assert workflow.steps[0].name == "main"
    assert workflow.steps[0].prompt_part == "Explain this code: {{ code }}"
    assert workflow.steps[0].is_prompt_part_step()
    assert workflow.source_path is None


def test_xprompt_to_workflow_preserves_inputs() -> None:
    """Test that conversion preserves input definitions."""
    inputs = [
        InputArg(name="code", type=InputType.TEXT),
        InputArg(name="language", type=InputType.WORD, default="python"),
    ]
    xp = XPrompt(name="review", content="Review {{ code }}", inputs=inputs)
    workflow = xprompt_to_workflow(xp)

    assert len(workflow.inputs) == 2
    assert workflow.inputs[0].name == "code"
    assert workflow.inputs[0].type == InputType.TEXT
    assert workflow.inputs[1].name == "language"
    assert workflow.inputs[1].default == "python"


def test_xprompt_to_workflow_preserves_source_path() -> None:
    """Test that conversion preserves source path."""
    xp = XPrompt(name="test", content="test content", source_path="/path/to/test.md")
    workflow = xprompt_to_workflow(xp)

    assert workflow.source_path == "/path/to/test.md"


def test_xprompt_to_workflow_is_simple_xprompt() -> None:
    """Test that converted xprompt is detected as simple."""
    xp = XPrompt(name="simple", content="Simple prompt")
    workflow = xprompt_to_workflow(xp)

    assert workflow.is_simple_xprompt()
    assert workflow.has_prompt_part()
    assert workflow.get_prompt_part_content() == "Simple prompt"


# Tests for create_adhoc_workflow


def test_create_adhoc_workflow_basic() -> None:
    """Test basic adhoc workflow creation."""
    workflow = create_adhoc_workflow("Hello world")

    assert workflow.name == "_adhoc"
    assert len(workflow.steps) == 1
    assert workflow.steps[0].name == "main"
    assert workflow.steps[0].prompt == "Hello world"
    assert workflow.steps[0].is_prompt_step()
    assert workflow.source_path is None
    assert workflow.inputs == []


def test_create_adhoc_workflow_not_simple_xprompt() -> None:
    """Test that adhoc workflow is NOT a simple xprompt (uses prompt, not prompt_part)."""
    workflow = create_adhoc_workflow("Test query")

    # Adhoc workflows use 'prompt' (full prompt step), not 'prompt_part'
    assert not workflow.is_simple_xprompt()
    assert not workflow.has_prompt_part()
    assert workflow.steps[0].prompt is not None


def test_create_adhoc_workflow_multiline_query() -> None:
    """Test adhoc workflow with multiline query."""
    query = """Please review this code:

def foo():
    pass"""
    workflow = create_adhoc_workflow(query)

    assert workflow.steps[0].prompt == query

"""Tests for the xprompt.models module."""

import pytest
from xprompt.models import InputArg, InputType, XPrompt, XPromptValidationError

# Tests for InputType enum


def test_input_type_values() -> None:
    """Test that InputType enum has expected values."""
    assert InputType.STRING.value == "string"
    assert InputType.INT.value == "int"
    assert InputType.BOOL.value == "bool"
    assert InputType.FLOAT.value == "float"


# Tests for InputArg.validate_and_convert


def test_input_arg_string_passthrough() -> None:
    """Test that string type passes through unchanged."""
    arg = InputArg(name="test", type=InputType.STRING)
    assert arg.validate_and_convert("hello") == "hello"
    assert arg.validate_and_convert("123") == "123"
    assert arg.validate_and_convert("") == ""


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


def test_input_arg_default_type_is_string() -> None:
    """Test that default type is STRING."""
    arg = InputArg(name="test")
    assert arg.type == InputType.STRING


def test_input_arg_default_is_none() -> None:
    """Test that default value is None."""
    arg = InputArg(name="test")
    assert arg.default is None


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
        InputArg(name="name", type=InputType.STRING),
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
        InputArg(name="alpha", type=InputType.STRING),
        InputArg(name="beta", type=InputType.INT),
    ]
    xp = XPrompt(name="test", content="", inputs=inputs)

    result = xp.get_input_by_name("beta")
    assert result is not None
    assert result.name == "beta"
    assert result.type == InputType.INT


def test_xprompt_get_input_by_name_not_found() -> None:
    """Test getting input by name when it doesn't exist."""
    inputs = [InputArg(name="alpha", type=InputType.STRING)]
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
        InputArg(name="first", type=InputType.STRING),
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
    inputs = [InputArg(name="first", type=InputType.STRING)]
    xp = XPrompt(name="test", content="", inputs=inputs)

    assert xp.get_input_by_position(-1) is None
    assert xp.get_input_by_position(1) is None
    assert xp.get_input_by_position(100) is None


def test_xprompt_get_input_by_position_empty_inputs() -> None:
    """Test getting input by position with no inputs defined."""
    xp = XPrompt(name="test", content="")
    assert xp.get_input_by_position(0) is None

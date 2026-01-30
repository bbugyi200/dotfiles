"""Tests for the xprompt output schema and validation modules."""

import tempfile
from pathlib import Path

from xprompt.loader import _load_xprompt_from_file, _parse_output_from_front_matter
from xprompt.output_processing import (
    extract_content_for_validation,
    inject_format_instructions,
    validate_output,
)
from xprompt.output_schema import OutputSchema, OutputType
from xprompt.validators import (
    OutputValidator,
    SplitSpecValidator,
    get_validator,
    register_validator,
)

# Tests for OutputSchema and OutputType


def test_output_type_enum_values() -> None:
    """Test OutputType enum has expected values."""
    assert OutputType.YAML_SCHEMA.value == "yaml_schema"


def test_output_schema_basic() -> None:
    """Test OutputSchema dataclass creation."""
    schema = OutputSchema(type=OutputType.YAML_SCHEMA)
    assert schema.type == OutputType.YAML_SCHEMA
    assert schema.validator is None
    assert schema.format_instructions is None


def test_output_schema_with_validator() -> None:
    """Test OutputSchema with validator specified."""
    schema = OutputSchema(type=OutputType.YAML_SCHEMA, validator="split_spec")
    assert schema.type == OutputType.YAML_SCHEMA
    assert schema.validator == "split_spec"


def test_output_schema_with_custom_instructions() -> None:
    """Test OutputSchema with custom format instructions."""
    schema = OutputSchema(
        type=OutputType.YAML_SCHEMA,
        format_instructions="Custom instructions here",
    )
    assert schema.format_instructions == "Custom instructions here"


# Tests for validator registry


def test_get_validator_split_spec() -> None:
    """Test that split_spec validator is registered."""
    validator_cls = get_validator("split_spec")
    assert validator_cls is not None
    assert validator_cls == SplitSpecValidator


def test_get_validator_unknown() -> None:
    """Test that unknown validator returns None."""
    validator_cls = get_validator("unknown_validator")
    assert validator_cls is None


def test_register_validator_decorator() -> None:
    """Test the register_validator decorator."""

    @register_validator("test_validator")
    class TestValidator(OutputValidator):
        def validate(self, content: str) -> tuple[bool, str | None]:
            del content  # Unused in test validator
            return (True, None)

        def get_format_instructions(self) -> str:
            return "Test instructions"

    validator_cls = get_validator("test_validator")
    assert validator_cls == TestValidator


# Tests for SplitSpecValidator


def test_split_spec_validator_valid_yaml() -> None:
    """Test SplitSpecValidator with valid YAML."""
    validator = SplitSpecValidator()
    yaml_content = """- name: test_first_change
  description: First change

- name: test_second_change
  description: Second change
"""
    is_valid, error = validator.validate(yaml_content)
    assert is_valid is True
    assert error is None


def test_split_spec_validator_invalid_yaml() -> None:
    """Test SplitSpecValidator with invalid YAML."""
    validator = SplitSpecValidator()
    yaml_content = "not: valid: yaml: content"
    is_valid, error = validator.validate(yaml_content)
    assert is_valid is False
    assert error is not None


def test_split_spec_validator_missing_name() -> None:
    """Test SplitSpecValidator with missing name field."""
    validator = SplitSpecValidator()
    yaml_content = """- description: Missing name field
"""
    is_valid, error = validator.validate(yaml_content)
    assert is_valid is False
    assert "name" in error.lower() if error else False


def test_split_spec_validator_format_instructions() -> None:
    """Test SplitSpecValidator returns format instructions."""
    validator = SplitSpecValidator()
    instructions = validator.get_format_instructions()
    assert isinstance(instructions, str)
    assert len(instructions) > 0
    assert "YAML" in instructions


# Tests for extract_content_for_validation


def test_extract_yaml_from_code_fence() -> None:
    """Test extracting YAML from markdown code fence."""
    response = """Here is the spec:
```yaml
- name: test_change
  description: Test
```
Done!"""
    extracted = extract_content_for_validation(response, OutputType.YAML_SCHEMA)
    assert extracted == "- name: test_change\n  description: Test"


def test_extract_yaml_from_yml_fence() -> None:
    """Test extracting YAML from yml code fence."""
    response = """```yml
- name: test
  description: Test
```"""
    extracted = extract_content_for_validation(response, OutputType.YAML_SCHEMA)
    assert extracted == "- name: test\n  description: Test"


def test_extract_yaml_no_fence() -> None:
    """Test extracting YAML when no code fence present."""
    response = """- name: test
  description: Test"""
    extracted = extract_content_for_validation(response, OutputType.YAML_SCHEMA)
    assert extracted == response


def test_extract_yaml_plain_fence() -> None:
    """Test extracting content from plain code fence (no language)."""
    response = """```
- name: test
  description: Test
```"""
    extracted = extract_content_for_validation(response, OutputType.YAML_SCHEMA)
    assert extracted == "- name: test\n  description: Test"


# Tests for inject_format_instructions


def test_inject_format_instructions_none_schema() -> None:
    """Test inject_format_instructions with None schema."""
    prompt = "Generate some output"
    result = inject_format_instructions(prompt, None)
    assert result == prompt


def test_inject_format_instructions_with_custom() -> None:
    """Test inject_format_instructions with custom instructions."""
    prompt = "Generate some output"
    schema = OutputSchema(
        type=OutputType.YAML_SCHEMA,
        format_instructions="Custom format instructions",
    )
    result = inject_format_instructions(prompt, schema)
    assert "Generate some output" in result
    assert "Custom format instructions" in result


def test_inject_format_instructions_from_validator() -> None:
    """Test inject_format_instructions uses validator instructions."""
    prompt = "Generate some output"
    schema = OutputSchema(type=OutputType.YAML_SCHEMA, validator="split_spec")
    result = inject_format_instructions(prompt, schema)
    assert "Generate some output" in result
    assert "YAML" in result  # Validator instructions should include YAML


def test_inject_format_instructions_custom_overrides_validator() -> None:
    """Test that custom instructions override validator instructions."""
    prompt = "Generate some output"
    schema = OutputSchema(
        type=OutputType.YAML_SCHEMA,
        validator="split_spec",
        format_instructions="Use my custom format",
    )
    result = inject_format_instructions(prompt, schema)
    assert "Use my custom format" in result


# Tests for validate_output


def test_validate_output_none_schema() -> None:
    """Test validate_output with None schema."""
    is_valid, error = validate_output("any content", None)
    assert is_valid is True
    assert error is None


def test_validate_output_no_validator() -> None:
    """Test validate_output with schema but no validator."""
    schema = OutputSchema(type=OutputType.YAML_SCHEMA)
    is_valid, error = validate_output("some content", schema)
    assert is_valid is True
    assert error is None


def test_validate_output_empty_content() -> None:
    """Test validate_output with empty content and no validator."""
    schema = OutputSchema(type=OutputType.YAML_SCHEMA)
    is_valid, error = validate_output("   ", schema)
    # Empty content is invalid when no validator is specified
    assert is_valid is False
    assert error == "Empty output"


def test_validate_output_with_validator_valid() -> None:
    """Test validate_output with validator - valid content."""
    schema = OutputSchema(type=OutputType.YAML_SCHEMA, validator="split_spec")
    content = """- name: test_change
  description: Test description
"""
    is_valid, error = validate_output(content, schema)
    assert is_valid is True
    assert error is None


def test_validate_output_with_validator_invalid() -> None:
    """Test validate_output with validator - invalid content."""
    schema = OutputSchema(type=OutputType.YAML_SCHEMA, validator="split_spec")
    content = "not valid yaml content"
    is_valid, error = validate_output(content, schema)
    assert is_valid is False
    assert error is not None


def test_validate_output_extracts_from_fence() -> None:
    """Test validate_output extracts content from code fences."""
    schema = OutputSchema(type=OutputType.YAML_SCHEMA, validator="split_spec")
    content = """Here is the spec:
```yaml
- name: test_change
  description: Test description
```
"""
    is_valid, error = validate_output(content, schema)
    assert is_valid is True
    assert error is None


# Tests for loader integration


def test_parse_output_from_front_matter_basic() -> None:
    """Test parsing output from front matter."""
    output_dict = {"type": "yaml_schema", "validator": "split_spec"}
    schema = _parse_output_from_front_matter(output_dict)

    assert schema is not None
    assert schema.type == OutputType.YAML_SCHEMA
    assert schema.validator == "split_spec"


def test_parse_output_from_front_matter_none() -> None:
    """Test parsing None output."""
    schema = _parse_output_from_front_matter(None)
    assert schema is None


def test_parse_output_from_front_matter_missing_type() -> None:
    """Test parsing output with missing type."""
    output_dict = {"validator": "split_spec"}
    schema = _parse_output_from_front_matter(output_dict)
    assert schema is None


def test_parse_output_from_front_matter_invalid_type() -> None:
    """Test parsing output with invalid type."""
    output_dict = {"type": "unknown_type", "validator": "split_spec"}
    schema = _parse_output_from_front_matter(output_dict)
    assert schema is None


def test_parse_output_from_front_matter_yaml_alias() -> None:
    """Test parsing output with 'yaml' type alias."""
    output_dict = {"type": "yaml"}
    schema = _parse_output_from_front_matter(output_dict)

    assert schema is not None
    assert schema.type == OutputType.YAML_SCHEMA


def test_parse_output_from_front_matter_with_instructions() -> None:
    """Test parsing output with custom format instructions."""
    output_dict = {
        "type": "yaml_schema",
        "format_instructions": "Custom instructions here",
    }
    schema = _parse_output_from_front_matter(output_dict)

    assert schema is not None
    assert schema.format_instructions == "Custom instructions here"


def test_load_xprompt_with_output_schema() -> None:
    """Test loading xprompt file with output schema."""
    content = """---
name: test_prompt
output:
  type: yaml_schema
  validator: split_spec
---
Generate a split spec."""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        temp_path = Path(f.name)

    try:
        xprompt = _load_xprompt_from_file(temp_path)

        assert xprompt is not None
        assert xprompt.name == "test_prompt"
        assert xprompt.output is not None
        assert xprompt.output.type == OutputType.YAML_SCHEMA
        assert xprompt.output.validator == "split_spec"
    finally:
        temp_path.unlink()


def test_load_xprompt_without_output_schema() -> None:
    """Test loading xprompt file without output schema."""
    file_content = """---
name: test_prompt
---
Just a prompt."""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(file_content)
        temp_path = Path(f.name)

    try:
        xprompt = _load_xprompt_from_file(temp_path)

        assert xprompt is not None
        assert xprompt.output is None
    finally:
        temp_path.unlink()

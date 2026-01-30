"""Tests for xprompt output validation module."""

import pytest
from xprompt.models import OutputSpec
from xprompt.output_validation import (
    OutputValidationError,
    extract_structured_content,
    generate_format_instructions,
    validate_against_schema,
    validate_response,
)


class TestExtractStructuredContent:
    """Tests for extract_structured_content function."""

    def test_extract_json_from_code_fence(self) -> None:
        """Test extracting JSON from markdown code fence."""
        response = '```json\n{"name": "test", "value": 42}\n```'
        data, format_type = extract_structured_content(response)
        assert data == {"name": "test", "value": 42}
        assert format_type == "json"

    def test_extract_json_from_plain_fence(self) -> None:
        """Test extracting JSON from plain code fence."""
        response = '```\n{"key": "value"}\n```'
        data, format_type = extract_structured_content(response)
        assert data == {"key": "value"}
        assert format_type == "json"

    def test_extract_json_from_raw_response(self) -> None:
        """Test extracting JSON when no code fence present."""
        response = '{"items": [1, 2, 3]}'
        data, format_type = extract_structured_content(response)
        assert data == {"items": [1, 2, 3]}
        assert format_type == "json"

    def test_extract_yaml_from_code_fence(self) -> None:
        """Test extracting YAML from markdown code fence."""
        response = "```yaml\nname: test\nvalue: 42\n```"
        data, format_type = extract_structured_content(response)
        assert data == {"name": "test", "value": 42}
        assert format_type == "yaml"

    def test_extract_from_multiple_fences_uses_first(self) -> None:
        """Test that first code fence is used when multiple present."""
        response = '```json\n{"first": true}\n```\n\n```json\n{"second": true}\n```'
        data, format_type = extract_structured_content(response)
        assert data == {"first": True}

    def test_invalid_content_raises_error(self) -> None:
        """Test that invalid content raises OutputValidationError."""
        response = "This is not JSON or YAML at all {{{invalid"
        with pytest.raises(OutputValidationError) as exc_info:
            extract_structured_content(response)
        assert "Could not extract valid JSON or YAML" in str(exc_info.value)
        assert exc_info.value.raw_response == response


class TestValidateAgainstSchema:
    """Tests for validate_against_schema function."""

    def test_valid_object_passes(self) -> None:
        """Test that valid data passes schema validation."""
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
            },
        }
        data = {"name": "test"}
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is True
        assert error is None

    def test_missing_required_field_fails(self) -> None:
        """Test that missing required field fails validation."""
        schema = {
            "type": "object",
            "required": ["name", "value"],
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "integer"},
            },
        }
        data = {"name": "test"}
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is False
        assert error is not None
        assert "value" in error

    def test_wrong_type_fails(self) -> None:
        """Test that wrong type fails validation."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
        }
        data = {"count": "not_an_integer"}
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is False
        assert error is not None

    def test_array_schema_validation(self) -> None:
        """Test array schema validation."""
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                },
            },
        }
        data = [{"name": "first"}, {"name": "second"}]
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is True
        assert error is None


class TestGenerateFormatInstructions:
    """Tests for generate_format_instructions function."""

    def test_generates_instructions_for_json_schema(self) -> None:
        """Test that format instructions are generated for json_schema type."""
        output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        )
        instructions = generate_format_instructions(output_spec)
        assert "OUTPUT FORMAT REQUIREMENTS" in instructions
        assert "JSON Schema" in instructions
        assert '"name"' in instructions

    def test_returns_empty_for_unknown_type(self) -> None:
        """Test that empty string is returned for unknown types."""
        output_spec = OutputSpec(
            type="unknown_type",
            schema={"some": "schema"},
        )
        instructions = generate_format_instructions(output_spec)
        assert instructions == ""


class TestValidateResponse:
    """Tests for validate_response function."""

    def test_valid_response_passes(self) -> None:
        """Test that valid response passes validation."""
        output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
        )
        response = '```json\n{"name": "test"}\n```'
        data, error = validate_response(response, output_spec)
        assert data == {"name": "test"}
        assert error is None

    def test_invalid_response_returns_error(self) -> None:
        """Test that invalid response returns error message."""
        output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "required": ["name", "value"],
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "integer"},
                },
            },
        )
        response = '```json\n{"name": "test"}\n```'  # Missing 'value'
        data, error = validate_response(response, output_spec)
        assert data == {"name": "test"}
        assert error is not None
        assert "value" in error

    def test_non_json_schema_type_passes_through(self) -> None:
        """Test that non-json_schema type passes response through."""
        output_spec = OutputSpec(
            type="custom_type",
            schema={},
        )
        response = "This is just plain text"
        data, error = validate_response(response, output_spec)
        assert data == response
        assert error is None

    def test_unparseable_response_raises_error(self) -> None:
        """Test that unparseable response raises OutputValidationError."""
        output_spec = OutputSpec(
            type="json_schema",
            schema={"type": "object"},
        )
        response = "This is not valid JSON at all {{{invalid"
        with pytest.raises(OutputValidationError):
            validate_response(response, output_spec)

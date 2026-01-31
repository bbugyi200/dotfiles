"""Tests for xprompt output validation module."""

import pytest
from xprompt.models import OutputSpec
from xprompt.output_validation import (
    OutputValidationError,
    _convert_semantic_schema_to_json_schema,
    _extract_semantic_type_hints,
    _validate_semantic_type,
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


class TestSemanticTypeValidation:
    """Tests for semantic output type validation."""

    def test_validate_semantic_type_word_valid(self) -> None:
        """Test that valid word passes validation."""
        result = _validate_semantic_type("hello", "word", "name")
        assert result is None

    def test_validate_semantic_type_word_with_space(self) -> None:
        """Test that word with space fails validation."""
        result = _validate_semantic_type("hello world", "word", "name")
        assert result is not None
        assert "expected word" in result
        assert "no spaces" in result

    def test_validate_semantic_type_word_with_tab(self) -> None:
        """Test that word with tab fails validation."""
        result = _validate_semantic_type("hello\tworld", "word", "name")
        assert result is not None
        assert "expected word" in result

    def test_validate_semantic_type_line_valid(self) -> None:
        """Test that valid line passes validation."""
        result = _validate_semantic_type("hello world", "line", "description")
        assert result is None

    def test_validate_semantic_type_line_with_newline(self) -> None:
        """Test that line with newline fails validation."""
        result = _validate_semantic_type("hello\nworld", "line", "description")
        assert result is not None
        assert "expected line" in result
        assert "no newlines" in result

    def test_validate_semantic_type_text_any_content(self) -> None:
        """Test that text allows any content including newlines."""
        result = _validate_semantic_type("hello\nworld\twith spaces", "text", "body")
        assert result is None

    def test_validate_semantic_type_path_valid(self) -> None:
        """Test that valid path passes validation."""
        result = _validate_semantic_type("/some/path/file.txt", "path", "file")
        assert result is None

    def test_validate_semantic_type_path_with_space(self) -> None:
        """Test that path with space fails validation."""
        result = _validate_semantic_type("/some path/file.txt", "path", "file")
        assert result is not None
        assert "expected path" in result
        assert "no spaces" in result

    def test_validate_semantic_type_string_no_validation(self) -> None:
        """Test that string type has no validation."""
        result = _validate_semantic_type("any content\nwith spaces", "string", "field")
        assert result is None

    def test_validate_semantic_type_non_string_skipped(self) -> None:
        """Test that non-string values skip validation."""
        result = _validate_semantic_type(42, "word", "count")
        assert result is None


class TestConvertSemanticSchema:
    """Tests for _convert_semantic_schema_to_json_schema function."""

    def test_convert_simple_word_type(self) -> None:
        """Test converting a simple word type."""
        schema = {"type": "word"}
        converted, type_map = _convert_semantic_schema_to_json_schema(schema)
        assert converted["type"] == "string"
        assert type_map.get("") == "word"

    def test_convert_nested_object_properties(self) -> None:
        """Test converting nested object properties."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "word"},
                "description": {"type": "text"},
            },
        }
        converted, type_map = _convert_semantic_schema_to_json_schema(schema)
        assert converted["properties"]["name"]["type"] == "string"
        assert converted["properties"]["description"]["type"] == "string"
        assert type_map.get("name") == "word"
        assert type_map.get("description") == "text"

    def test_convert_array_items(self) -> None:
        """Test converting array items."""
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "word"},
                },
            },
        }
        converted, type_map = _convert_semantic_schema_to_json_schema(schema)
        assert converted["items"]["properties"]["name"]["type"] == "string"
        assert type_map.get("[].name") == "word"

    def test_preserve_standard_json_schema_types(self) -> None:
        """Test that standard JSON Schema types are preserved."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "active": {"type": "boolean"},
            },
        }
        converted, type_map = _convert_semantic_schema_to_json_schema(schema)
        assert converted["properties"]["count"]["type"] == "integer"
        assert converted["properties"]["active"]["type"] == "boolean"
        assert len(type_map) == 0


class TestValidateAgainstSchemaWithSemanticTypes:
    """Tests for validate_against_schema with semantic types."""

    def test_valid_word_passes(self) -> None:
        """Test that valid word data passes validation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "word"},
            },
        }
        data = {"name": "hello"}
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is True
        assert error is None

    def test_word_with_space_fails(self) -> None:
        """Test that word with space fails validation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "word"},
            },
        }
        data = {"name": "hello world"}
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is False
        assert error is not None
        assert "expected word" in error

    def test_line_with_newline_fails(self) -> None:
        """Test that line with newline fails validation."""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "line"},
            },
        }
        data = {"title": "Hello\nWorld"}
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is False
        assert error is not None
        assert "expected line" in error

    def test_array_item_validation(self) -> None:
        """Test semantic validation on array items."""
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "word"},
                },
            },
        }
        # Valid data
        data = [{"name": "first"}, {"name": "second"}]
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is True

        # Invalid data with space in name
        data_invalid: list[dict[str, str]] = [{"name": "first item"}]
        is_valid, error = validate_against_schema(data_invalid, schema)
        assert is_valid is False
        assert error is not None and "expected word" in error

    def test_json_schema_validation_before_semantic(self) -> None:
        """Test that JSON Schema validation happens before semantic validation."""
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "word"},
            },
        }
        # Missing required field - should fail JSON Schema validation
        data: dict[str, str] = {}
        is_valid, error = validate_against_schema(data, schema)
        assert is_valid is False
        assert error is not None and "name" in error


class TestExtractSemanticTypeHints:
    """Tests for _extract_semantic_type_hints function."""

    def test_extract_word_hint(self) -> None:
        """Test extracting hint for word type."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "word"},
            },
        }
        hints = _extract_semantic_type_hints(schema)
        assert len(hints) == 1
        assert "name" in hints[0]
        assert "single word" in hints[0]

    def test_extract_line_hint(self) -> None:
        """Test extracting hint for line type."""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "line"},
            },
        }
        hints = _extract_semantic_type_hints(schema)
        assert len(hints) == 1
        assert "title" in hints[0]
        assert "single line" in hints[0]

    def test_extract_path_hint(self) -> None:
        """Test extracting hint for path type."""
        schema = {
            "type": "object",
            "properties": {
                "file": {"type": "path"},
            },
        }
        hints = _extract_semantic_type_hints(schema)
        assert len(hints) == 1
        assert "file" in hints[0]
        assert "valid path" in hints[0]

    def test_no_hint_for_text_type(self) -> None:
        """Test that text type produces no hint (no constraints)."""
        schema = {
            "type": "object",
            "properties": {
                "body": {"type": "text"},
            },
        }
        hints = _extract_semantic_type_hints(schema)
        assert len(hints) == 0

    def test_no_hint_for_string_type(self) -> None:
        """Test that string type produces no hint."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
        }
        hints = _extract_semantic_type_hints(schema)
        assert len(hints) == 0

    def test_multiple_hints_from_nested_schema(self) -> None:
        """Test extracting multiple hints from nested schema."""
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "word"},
                    "description": {"type": "text"},
                    "parent": {"type": "word"},
                },
            },
        }
        hints = _extract_semantic_type_hints(schema)
        assert len(hints) == 2  # name and parent are word types
        names_mentioned = [h for h in hints if "name" in h]
        parent_mentioned = [h for h in hints if "parent" in h]
        assert len(names_mentioned) == 1
        assert len(parent_mentioned) == 1


class TestGenerateFormatInstructionsWithSemanticTypes:
    """Tests for generate_format_instructions with semantic types."""

    def test_includes_semantic_constraints(self) -> None:
        """Test that format instructions include semantic type constraints."""
        output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "properties": {
                    "name": {"type": "word"},
                    "title": {"type": "line"},
                },
            },
        )
        instructions = generate_format_instructions(output_spec)
        assert "FIELD CONSTRAINTS" in instructions
        assert "name" in instructions
        assert "single word" in instructions
        assert "title" in instructions
        assert "single line" in instructions

    def test_no_constraints_section_when_no_semantic_types(self) -> None:
        """Test that FIELD CONSTRAINTS is omitted when no semantic types."""
        output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
            },
        )
        instructions = generate_format_instructions(output_spec)
        assert "FIELD CONSTRAINTS" not in instructions

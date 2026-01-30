"""XPrompt system for typed prompt templates with argument validation.

This module provides a replacement for the legacy snippet system, adding:
- Markdown files with YAML front matter for defining input arguments
- Multiple discovery locations with priority ordering
- Type validation for input arguments
- Backward compatibility with existing #name(args) syntax
"""

from .loader import get_all_snippets, get_all_xprompts
from .models import InputArg, InputType, OutputSpec, XPrompt, XPromptValidationError
from .output_validation import (
    OutputValidationError,
    extract_structured_content,
    generate_format_instructions,
    validate_against_schema,
    validate_response,
)
from .processor import (
    get_primary_output_schema,
    is_jinja2_template,
    process_snippet_references,
    process_xprompt_references,
    render_toplevel_jinja2,
)

__all__ = [
    # Models
    "InputArg",
    "InputType",
    "OutputSpec",
    "XPrompt",
    "XPromptValidationError",
    # Output validation
    "OutputValidationError",
    "extract_structured_content",
    "generate_format_instructions",
    "validate_against_schema",
    "validate_response",
    # Loader
    "get_all_snippets",
    "get_all_xprompts",
    # Processor
    "get_primary_output_schema",
    "is_jinja2_template",
    "process_snippet_references",
    "process_xprompt_references",
    "render_toplevel_jinja2",
]

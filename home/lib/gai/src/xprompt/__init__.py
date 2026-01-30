"""XPrompt system for typed prompt templates with argument validation.

This module provides a replacement for the legacy snippet system, adding:
- Markdown files with YAML front matter for defining input arguments
- Multiple discovery locations with priority ordering
- Type validation for input arguments
- Backward compatibility with existing #name(args) syntax
- Output schema validation for agent responses
"""

from .loader import get_all_snippets, get_all_xprompts
from .models import InputArg, InputType, XPrompt, XPromptValidationError
from .output_processing import (
    extract_content_for_validation,
    inject_format_instructions,
    validate_output,
)
from .output_schema import OutputSchema, OutputType
from .processor import (
    XPromptExpansionResult,
    is_jinja2_template,
    process_snippet_references,
    process_xprompt_references,
    process_xprompt_references_with_metadata,
    render_toplevel_jinja2,
)

__all__ = [
    # Models
    "InputArg",
    "InputType",
    "XPrompt",
    "XPromptValidationError",
    # Output schema
    "OutputSchema",
    "OutputType",
    # Output processing
    "extract_content_for_validation",
    "inject_format_instructions",
    "validate_output",
    # Loader
    "get_all_snippets",
    "get_all_xprompts",
    # Processor
    "XPromptExpansionResult",
    "is_jinja2_template",
    "process_snippet_references",
    "process_xprompt_references",
    "process_xprompt_references_with_metadata",
    "render_toplevel_jinja2",
]

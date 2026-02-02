"""XPrompt system for typed prompt templates with argument validation.

This module provides a replacement for the legacy snippet system, adding:
- Markdown files with YAML front matter for defining input arguments
- Multiple discovery locations with priority ordering
- Type validation for input arguments
- Backward compatibility with existing #name(args) syntax
- YAML workflow support for multi-step agent workflows
"""

from .loader import (
    get_all_workflows,
    get_all_xprompts,
    get_xprompt_or_workflow,
)
from .models import InputArg, InputType, OutputSpec, XPrompt, XPromptValidationError
from .output_validation import (
    OutputValidationError,
    extract_structured_content,
    generate_format_instructions,
    validate_against_schema,
    validate_response,
)
from .processor import (
    execute_workflow,
    get_primary_output_schema,
    is_jinja2_template,
    is_workflow_reference,
    process_xprompt_references,
    render_toplevel_jinja2,
)
from .workflow_executor import HITLHandler, HITLResult, WorkflowExecutor
from .workflow_hitl import CLIHITLHandler
from .workflow_models import (
    StepState,
    StepStatus,
    Workflow,
    WorkflowError,
    WorkflowExecutionError,
    WorkflowState,
    WorkflowStep,
    WorkflowValidationError,
)
from .workflow_output import LoopInfo, WorkflowOutputHandler

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
    "get_all_workflows",
    "get_all_xprompts",
    "get_xprompt_or_workflow",
    # Processor
    "execute_workflow",
    "get_primary_output_schema",
    "is_jinja2_template",
    "is_workflow_reference",
    "process_xprompt_references",
    "render_toplevel_jinja2",
    # Workflow models
    "StepState",
    "StepStatus",
    "Workflow",
    "WorkflowError",
    "WorkflowExecutionError",
    "WorkflowExecutor",
    "WorkflowState",
    "WorkflowStep",
    "WorkflowValidationError",
    # Workflow execution
    "CLIHITLHandler",
    "HITLHandler",
    "HITLResult",
    # Workflow output
    "LoopInfo",
    "WorkflowOutputHandler",
]

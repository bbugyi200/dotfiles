"""Workflow data models for multi-step agent workflows."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from xprompt.models import InputArg, OutputSpec


class StepStatus(Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowStep:
    """Definition of a single step in a workflow.

    Attributes:
        name: Step identifier (defaults to step_{index} if not specified).
        agent: XPrompt name to invoke (mutually exclusive with bash/python).
        bash: Bash command to execute (mutually exclusive with agent/python).
        python: Python code to execute (mutually exclusive with agent/bash).
        prompt: Prompt template for agent steps (supports Jinja2 and xprompt refs).
        output: Output specification for validation.
        hitl: Whether to require human-in-the-loop approval.
    """

    name: str
    agent: str | None = None
    bash: str | None = None
    python: str | None = None
    prompt: str | None = None
    output: OutputSpec | None = None
    hitl: bool = False

    def is_agent_step(self) -> bool:
        """Return True if this is an agent step."""
        return self.agent is not None

    def is_bash_step(self) -> bool:
        """Return True if this is a bash step."""
        return self.bash is not None

    def is_python_step(self) -> bool:
        """Return True if this is a python step."""
        return self.python is not None


@dataclass
class WorkflowConfig:
    """Configuration options for automatic workflow resource management.

    Attributes:
        claim_workspace: Auto-manage workspace claiming/releasing.
        create_artifacts: Auto-create artifacts directory.
        log_workflow: Auto-initialize/finalize gai.md log.
    """

    claim_workspace: bool = False
    create_artifacts: bool = False
    log_workflow: bool = False


@dataclass
class Workflow:
    """A multi-step agent workflow definition.

    Attributes:
        name: Workflow identifier (used in #name syntax).
        inputs: List of input argument definitions.
        steps: Ordered list of workflow steps to execute.
        config: Automatic resource management configuration.
        source_path: File path where workflow was loaded from.
    """

    name: str
    inputs: list[InputArg] = field(default_factory=list)
    steps: list[WorkflowStep] = field(default_factory=list)
    config: WorkflowConfig = field(default_factory=WorkflowConfig)
    source_path: str | None = None

    def get_input_by_name(self, name: str) -> InputArg | None:
        """Get an input argument definition by name.

        Args:
            name: The argument name to look up.

        Returns:
            The InputArg if found, None otherwise.
        """
        for input_arg in self.inputs:
            if input_arg.name == name:
                return input_arg
        return None


@dataclass
class StepState:
    """Runtime state of a workflow step.

    Attributes:
        name: Step identifier.
        status: Current execution status.
        output: Step output data (if completed).
        error: Error message (if failed).
    """

    name: str
    status: StepStatus = StepStatus.PENDING
    output: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class WorkflowState:
    """Runtime state of a workflow execution.

    Attributes:
        workflow_name: Name of the workflow being executed.
        status: Overall workflow status.
        current_step_index: Index of step currently executing.
        steps: State of each step.
        context: Accumulated context (inputs + step outputs).
        artifacts_dir: Directory for workflow artifacts.
        start_time: ISO timestamp when workflow started.
    """

    workflow_name: str
    status: str  # "running", "waiting_hitl", "completed", "failed"
    current_step_index: int
    steps: list[StepState]
    context: dict[str, Any]
    artifacts_dir: str
    start_time: str


class WorkflowError(Exception):
    """Base exception for workflow errors."""

    pass


class WorkflowValidationError(WorkflowError):
    """Raised when workflow validation fails."""

    pass


class WorkflowExecutionError(WorkflowError):
    """Raised when workflow execution fails."""

    pass

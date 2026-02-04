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
    SKIPPED = "skipped"


@dataclass
class LoopConfig:
    """Configuration for repeat:/until: and while: loops.

    Attributes:
        condition: Jinja2 condition expression (until: for repeat, condition: for while).
        max_iterations: Maximum iterations before raising error (default: 100).
    """

    condition: str
    max_iterations: int = 100


@dataclass
class ParallelConfig:
    """Configuration for parallel step execution.

    Attributes:
        steps: List of workflow steps to execute in parallel.
        fail_fast: If True, cancel remaining steps on first failure.
    """

    steps: list["WorkflowStep"]
    fail_fast: bool = True


@dataclass
class WorkflowStep:
    """Definition of a single step in a workflow.

    Attributes:
        name: Step identifier (defaults to step_{index} if not specified).
        prompt: Prompt template for prompt steps (supports Jinja2 and xprompt refs).
            Mutually exclusive with bash/python/parallel/prompt_part.
        bash: Bash command to execute (mutually exclusive with prompt/python/parallel/prompt_part).
        python: Python code to execute (mutually exclusive with prompt/bash/parallel/prompt_part).
        prompt_part: Content to append to containing prompt when workflow is embedded.
            Mutually exclusive with prompt/bash/python/parallel.
        output: Output specification for validation.
        hitl: Whether to require human-in-the-loop approval.
        hidden: If true, this step is hidden by default in the Agents tab TUI.
        condition: if: condition (Jinja2 expression) - step skipped if false.
        for_loop: for: loop config {var: expression} for iteration over lists.
        repeat_config: repeat: loop config with until: condition.
        while_config: while: loop config with condition: to check before iterations.
        parallel_config: parallel: config for running nested steps concurrently.
        join: How to collect iteration results (array, text, object, lastOf).
    """

    name: str
    prompt: str | None = None
    bash: str | None = None
    python: str | None = None
    prompt_part: str | None = None
    output: OutputSpec | None = None
    hitl: bool = False
    hidden: bool = False
    condition: str | None = None
    for_loop: dict[str, str] | None = None
    repeat_config: LoopConfig | None = None
    while_config: LoopConfig | None = None
    parallel_config: ParallelConfig | None = None
    join: str | None = None

    def is_prompt_step(self) -> bool:
        """Return True if this is a prompt step."""
        return self.prompt is not None

    def is_bash_step(self) -> bool:
        """Return True if this is a bash step."""
        return self.bash is not None

    def is_python_step(self) -> bool:
        """Return True if this is a python step."""
        return self.python is not None

    def is_parallel_step(self) -> bool:
        """Return True if this is a parallel step."""
        return self.parallel_config is not None

    def is_prompt_part_step(self) -> bool:
        """Return True if this is a prompt_part step."""
        return self.prompt_part is not None


@dataclass
class Workflow:
    """A multi-step agent workflow definition.

    Attributes:
        name: Workflow identifier (used in #name syntax).
        inputs: List of input argument definitions.
        steps: Ordered list of workflow steps to execute.
        source_path: File path where workflow was loaded from.
    """

    name: str
    inputs: list[InputArg] = field(default_factory=list)
    steps: list[WorkflowStep] = field(default_factory=list)
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

    def get_prompt_part_index(self) -> int | None:
        """Get the index of the prompt_part step if present.

        Returns:
            The index of the prompt_part step, or None if not present.
        """
        for i, step in enumerate(self.steps):
            if step.is_prompt_part_step():
                return i
        return None

    def has_prompt_part(self) -> bool:
        """Check if this workflow has a prompt_part step.

        Returns:
            True if the workflow has a prompt_part step.
        """
        return self.get_prompt_part_index() is not None

    def get_prompt_part_content(self) -> str:
        """Get the prompt_part content if present.

        Returns:
            The prompt_part content, or empty string if not present.
        """
        idx = self.get_prompt_part_index()
        if idx is not None:
            return self.steps[idx].prompt_part or ""
        return ""

    def get_pre_prompt_steps(self) -> list[WorkflowStep]:
        """Get steps that run before the prompt_part step.

        Returns:
            List of steps before prompt_part, or empty list if no prompt_part.
        """
        idx = self.get_prompt_part_index()
        if idx is None:
            return []
        return self.steps[:idx]

    def get_post_prompt_steps(self) -> list[WorkflowStep]:
        """Get steps that run after the prompt_part step.

        Returns:
            List of steps after prompt_part, or all steps if no prompt_part.
        """
        idx = self.get_prompt_part_index()
        if idx is None:
            return list(self.steps)
        return self.steps[idx + 1 :]

    def appears_as_agent(self) -> bool:
        """Check if workflow should appear as an 'agent' entry.

        Returns True if all non-prompt steps are hidden, meaning the workflow
        should display as a simple [run] entry instead of [workflow:name].
        """
        visible_steps = [s for s in self.steps if not s.hidden]
        return len(visible_steps) == 1 and visible_steps[0].is_prompt_step()

    def is_simple_xprompt(self) -> bool:
        """Check if workflow is a simple xprompt (single prompt_part step only).

        Returns True for converted xprompts that can be expanded inline as pure
        text substitution. This is the prompt_part equivalent of appears_as_agent().

        A simple xprompt has:
        - Exactly one step
        - That step is a prompt_part step (not prompt, bash, python, or parallel)

        These workflows can be:
        - Expanded inline when embedded in other prompts
        - Executed as direct prompts when run standalone
        """
        return len(self.steps) == 1 and self.has_prompt_part()


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

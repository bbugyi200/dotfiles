"""Custom agent workflow mixin for the ace TUI app."""

from .._agent_workflow_launch import AgentLaunchMixin
from ._editor import EditorMixin
from ._entry_points import EntryPointsMixin
from ._prompt_bar import PromptBarMixin


class AgentWorkflowMixin(
    EntryPointsMixin,
    PromptBarMixin,
    EditorMixin,
    AgentLaunchMixin,
):
    """Mixin providing custom agent workflow actions."""

    pass

"""Hint-based action methods for the ace TUI app."""

from ._accept import AcceptMailMixin
from ._files import FileViewingMixin
from ._hooks import HookEditingMixin
from ._processing import InputProcessingMixin


class HintActionsMixin(
    AcceptMailMixin,
    FileViewingMixin,
    HookEditingMixin,
    InputProcessingMixin,
):
    """Mixin providing hint-based actions (edit hooks, view files)."""

    pass

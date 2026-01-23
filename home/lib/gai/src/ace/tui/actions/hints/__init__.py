"""Hint-based action methods for the ace TUI app."""

from ._accept import AcceptMailMixin
from ._files import FileViewingMixin
from ._hooks import HookEditingMixin
from ._processing import InputProcessingMixin
from ._rewind import RewindMixin


class HintActionsMixin(
    AcceptMailMixin,
    FileViewingMixin,
    HookEditingMixin,
    InputProcessingMixin,
    RewindMixin,
):
    """Mixin providing hint-based actions (edit hooks, view files, rewind)."""

    pass

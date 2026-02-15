"""Factory and auto-detection for VCS providers."""

import os

from ._base import VCSProvider
from ._errors import VCSProviderNotFoundError

# provider-name → provider-class
_PROVIDERS: dict[str, type[VCSProvider]] = {}


def register_provider(name: str, cls: type[VCSProvider]) -> None:
    """Register a VCS provider class under *name* (e.g. ``"hg"``)."""
    _PROVIDERS[name] = cls


def detect_vcs(cwd: str) -> str | None:
    """Walk up from *cwd* looking for ``.hg/`` or ``.git/``.

    Returns the provider name (``"hg"`` or ``"git"``) or ``None``.
    """
    directory = os.path.abspath(cwd)
    while True:
        if os.path.isdir(os.path.join(directory, ".hg")):
            return "hg"
        if os.path.isdir(os.path.join(directory, ".git")):
            return "git"
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return None


def get_vcs_provider(cwd: str) -> VCSProvider:
    """Return a :class:`VCSProvider` instance for *cwd*.

    Walks up the directory tree to detect ``.hg/`` or ``.git/`` and
    returns the matching registered provider.

    Raises:
        VCSProviderNotFoundError: If no VCS directory is found or no
            provider is registered for the detected VCS type.
    """
    # Ensure providers are loaded
    _ensure_providers_loaded()

    vcs_name = detect_vcs(cwd)
    if vcs_name is None:
        raise VCSProviderNotFoundError(cwd)
    cls = _PROVIDERS.get(vcs_name)
    if cls is None:
        raise VCSProviderNotFoundError(cwd)
    return cls()


def _ensure_providers_loaded() -> None:
    """Import provider modules so they self-register."""
    if _PROVIDERS:
        return
    # Import triggers register_provider() at module level
    from . import _git as _git  # noqa: F401
    from . import _hg as _hg  # noqa: F401

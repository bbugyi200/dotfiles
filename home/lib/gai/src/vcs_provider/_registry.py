"""Factory and auto-detection for VCS providers."""

import os

from ._base import VCSProvider
from ._errors import VCSProviderNotFoundError
from .config import get_vcs_provider_config

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


def _resolve_vcs_name(cwd: str) -> str | None:
    """Determine the VCS provider name to use.

    Resolution order:
    1. Env var ``GAI_VCS_PROVIDER`` (if set and not ``"auto"``)
    2. Config ``vcs_provider.provider`` from gai.yml (if set and not ``"auto"``)
    3. ``detect_vcs(cwd)`` (auto-detection)
    """
    # 1. Environment variable override
    env_val = os.environ.get("GAI_VCS_PROVIDER")
    if env_val and env_val != "auto":
        return env_val

    # 2. Config file override (only if env var didn't short-circuit)
    if not env_val:
        config = get_vcs_provider_config()
        config_provider = config.get("provider")
        if config_provider and config_provider != "auto":
            return config_provider

    # 3. Auto-detection
    return detect_vcs(cwd)


def get_vcs_provider(cwd: str) -> VCSProvider:
    """Return a :class:`VCSProvider` instance for *cwd*.

    Uses :func:`_resolve_vcs_name` to determine the provider, which
    checks env var, config, and auto-detection in that order.

    Raises:
        VCSProviderNotFoundError: If no VCS directory is found or no
            provider is registered for the detected VCS type.
    """
    # Ensure providers are loaded
    _ensure_providers_loaded()

    vcs_name = _resolve_vcs_name(cwd)
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

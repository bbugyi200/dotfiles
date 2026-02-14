"""VCS provider abstraction layer.

Usage::

    from vcs_provider import get_vcs_provider

    provider = get_vcs_provider(workspace_dir)
    success, error = provider.checkout("my_branch", workspace_dir)
"""

from ._base import VCSProvider
from ._errors import VCSOperationError, VCSProviderNotFoundError
from ._registry import get_vcs_provider, register_provider

__all__ = [
    "VCSOperationError",
    "VCSProvider",
    "VCSProviderNotFoundError",
    "get_vcs_provider",
    "register_provider",
]

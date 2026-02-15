"""Configuration reader for the VCS provider layer."""

import os
from typing import Any

import yaml  # type: ignore[import-untyped]


def get_vcs_provider_config() -> dict[str, Any]:
    """Read the ``vcs_provider`` section from ``gai.yml``.

    Looks for ``~/.config/gai/gai.yml`` and returns the ``vcs_provider``
    section, or an empty dict if not found.

    Returns:
        The vcs_provider configuration dict.
    """
    config_path = os.path.expanduser("~/.config/gai/gai.yml")
    if not os.path.exists(config_path):
        return {}

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return {}

        return data.get("vcs_provider", {}) or {}
    except Exception:
        return {}

"""Axe scheduler configuration loading."""

import os
from dataclasses import dataclass

import yaml  # type: ignore[import-untyped]


@dataclass
class _AxeConfig:
    """Configuration for the axe scheduler."""

    full_check_interval: int = 300
    comment_check_interval: int = 60
    hook_interval: int = 1
    zombie_timeout_seconds: int = 7200
    max_runners: int = 5


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def load_axe_config() -> _AxeConfig:
    """Load axe config from gai.yml, returning defaults if section missing."""
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        return _AxeConfig()

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "axe" not in data:
        return _AxeConfig()

    axe_data = data["axe"]
    if not isinstance(axe_data, dict):
        return _AxeConfig()

    return _AxeConfig(
        full_check_interval=axe_data.get(
            "full_check_interval", _AxeConfig.full_check_interval
        ),
        comment_check_interval=axe_data.get(
            "comment_check_interval", _AxeConfig.comment_check_interval
        ),
        hook_interval=axe_data.get("hook_interval", _AxeConfig.hook_interval),
        zombie_timeout_seconds=axe_data.get(
            "zombie_timeout_seconds", _AxeConfig.zombie_timeout_seconds
        ),
        max_runners=axe_data.get("max_runners", _AxeConfig.max_runners),
    )

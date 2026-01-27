"""Shared test utilities for gai tests."""

import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


@contextmanager
def mentor_config_from_yaml(yaml_content: str) -> Generator[str, None, None]:
    """Context manager that creates a temp YAML config and patches _get_config_path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        with patch("mentor_config._get_config_path", return_value=config_path):
            yield config_path
    finally:
        Path(config_path).unlink()

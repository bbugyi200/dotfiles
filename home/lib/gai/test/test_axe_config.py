"""Tests for the axe_config module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from axe_config import _AxeConfig, load_axe_config


def test_load_axe_config_all_fields() -> None:
    """Test loading config with all fields present."""
    yaml_content = """
axe:
  full_check_interval: 600
  comment_check_interval: 120
  hook_interval: 5
  zombie_timeout_seconds: 3600
  max_runners: 10
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("axe_config._get_config_path", return_value=config_path):
        config = load_axe_config()

    assert config.full_check_interval == 600
    assert config.comment_check_interval == 120
    assert config.hook_interval == 5
    assert config.zombie_timeout_seconds == 3600
    assert config.max_runners == 10

    Path(config_path).unlink()


def test_load_axe_config_partial_fields() -> None:
    """Test loading config with partial fields uses defaults for missing."""
    yaml_content = """
axe:
  full_check_interval: 600
  max_runners: 10
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("axe_config._get_config_path", return_value=config_path):
        config = load_axe_config()

    assert config.full_check_interval == 600
    assert config.comment_check_interval == 60
    assert config.hook_interval == 1
    assert config.zombie_timeout_seconds == 7200
    assert config.max_runners == 10

    Path(config_path).unlink()


def test_load_axe_config_no_axe_section() -> None:
    """Test loading config with no axe section returns all defaults."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit_test
    output_regex: "test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("axe_config._get_config_path", return_value=config_path):
        config = load_axe_config()

    assert config == _AxeConfig()

    Path(config_path).unlink()


def test_load_axe_config_missing_file() -> None:
    """Test loading config with missing file returns all defaults."""
    with patch("axe_config._get_config_path", return_value="/nonexistent/path.yml"):
        config = load_axe_config()

    assert config == _AxeConfig()


def test_load_axe_config_axe_section_not_dict() -> None:
    """Test loading config when axe section is not a dict returns defaults."""
    yaml_content = """
axe: "not a dict"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("axe_config._get_config_path", return_value=config_path):
        config = load_axe_config()

    assert config == _AxeConfig()

    Path(config_path).unlink()


def test_load_axe_config_data_not_dict() -> None:
    """Test loading config when top-level data is not a dict returns defaults."""
    yaml_content = """
- just_a_list
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("axe_config._get_config_path", return_value=config_path):
        config = load_axe_config()

    assert config == _AxeConfig()

    Path(config_path).unlink()

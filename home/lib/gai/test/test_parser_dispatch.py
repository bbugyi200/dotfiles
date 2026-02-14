"""Tests for parse_project_file dispatch and find_all_changespecs YAML preference."""

import os
from pathlib import Path
from unittest.mock import patch

import yaml  # type: ignore[import-untyped]
from ace.changespec import find_all_changespecs, parse_project_file
from ace.changespec.locking import write_changespec_atomic
from ace.changespec.models import ChangeSpec
from ace.changespec.project_spec import ProjectSpec, serialize_project_spec

# --- Helper to build a minimal .gp file content ---


def _make_gp_content(name: str = "test-cl", status: str = "WIP") -> str:
    return f"## ChangeSpec\nNAME: {name}\nDESCRIPTION:\n  A test change\nSTATUS: {status}\n"


def _make_yaml_content(
    name: str = "test-cl",
    status: str = "WIP",
    file_path: str = "/tmp/test.yaml",
) -> str:
    spec = ProjectSpec(
        file_path=file_path,
        changespecs=[
            ChangeSpec(
                name=name,
                description="A test change",
                parent=None,
                cl=None,
                status=status,
                test_targets=None,
                kickstart=None,
                file_path=file_path,
                line_number=0,
            )
        ],
    )
    return serialize_project_spec(spec)


# --- Dispatch tests ---


def test_gp_file_dispatches_to_markdown_parser(tmp_path: Path) -> None:
    """A .gp file is parsed by the markdown parser."""
    gp_file = tmp_path / "proj.gp"
    gp_file.write_text(_make_gp_content("my-cl"))

    result = parse_project_file(str(gp_file))

    assert len(result) == 1
    assert result[0].name == "my-cl"
    assert result[0].status == "WIP"


def test_yaml_file_dispatches_to_yaml_parser(tmp_path: Path) -> None:
    """A .yaml file is parsed by the YAML parser."""
    yaml_file = tmp_path / "proj.yaml"
    yaml_file.write_text(_make_yaml_content("yaml-cl", file_path=str(yaml_file)))

    result = parse_project_file(str(yaml_file))

    assert len(result) == 1
    assert result[0].name == "yaml-cl"
    assert result[0].status == "WIP"


def test_yml_extension_dispatches_to_yaml_parser(tmp_path: Path) -> None:
    """A .yml file is also parsed by the YAML parser."""
    yml_file = tmp_path / "proj.yml"
    yml_file.write_text(_make_yaml_content("yml-cl", file_path=str(yml_file)))

    result = parse_project_file(str(yml_file))

    assert len(result) == 1
    assert result[0].name == "yml-cl"


def test_empty_yaml_file_returns_empty_list(tmp_path: Path) -> None:
    """An empty .yaml file returns an empty list."""
    yaml_file = tmp_path / "empty.yaml"
    yaml_file.write_text("")

    result = parse_project_file(str(yaml_file))

    assert result == []


def test_yaml_no_changespecs_key_returns_empty_list(tmp_path: Path) -> None:
    """A .yaml file with no changespecs key returns an empty list."""
    yaml_file = tmp_path / "nochangespecs.yaml"
    yaml_file.write_text(yaml.dump({"bug": "b/123"}))

    result = parse_project_file(str(yaml_file))

    assert result == []


def test_empty_gp_file_returns_empty_list(tmp_path: Path) -> None:
    """An empty .gp file returns an empty list."""
    gp_file = tmp_path / "empty.gp"
    gp_file.write_text("")

    result = parse_project_file(str(gp_file))

    assert result == []


def test_file_path_metadata_preserved_gp(tmp_path: Path) -> None:
    """file_path metadata is set for .gp parsed changespecs."""
    gp_file = tmp_path / "proj.gp"
    gp_file.write_text(_make_gp_content())

    result = parse_project_file(str(gp_file))

    assert result[0].file_path == str(gp_file)


def test_file_path_metadata_preserved_yaml(tmp_path: Path) -> None:
    """file_path metadata is set for .yaml parsed changespecs."""
    yaml_file = tmp_path / "proj.yaml"
    yaml_file.write_text(_make_yaml_content(file_path=str(yaml_file)))

    result = parse_project_file(str(yaml_file))

    assert result[0].file_path == str(yaml_file)


# --- find_all_changespecs preference tests ---


def test_find_all_changespecs_prefers_yaml(tmp_path: Path) -> None:
    """When both .yaml and .gp exist, .yaml is preferred."""
    proj_dir = tmp_path / ".gai" / "projects" / "myproj"
    proj_dir.mkdir(parents=True)

    yaml_file = proj_dir / "myproj.yaml"
    gp_file = proj_dir / "myproj.gp"
    yaml_file.write_text(_make_yaml_content("yaml-cl", file_path=str(yaml_file)))
    gp_file.write_text(_make_gp_content("gp-cl"))

    with patch("ace.changespec.Path.home", return_value=tmp_path):
        result = find_all_changespecs()

    assert len(result) == 1
    assert result[0].name == "yaml-cl"


def test_find_all_changespecs_falls_back_to_gp(tmp_path: Path) -> None:
    """When only .gp exists, it is used."""
    proj_dir = tmp_path / ".gai" / "projects" / "myproj"
    proj_dir.mkdir(parents=True)

    gp_file = proj_dir / "myproj.gp"
    gp_file.write_text(_make_gp_content("gp-cl"))

    with patch("ace.changespec.Path.home", return_value=tmp_path):
        result = find_all_changespecs()

    assert len(result) == 1
    assert result[0].name == "gp-cl"


def test_find_all_changespecs_skips_dir_with_no_project_file(tmp_path: Path) -> None:
    """A project dir with neither .yaml nor .gp is skipped."""
    proj_dir = tmp_path / ".gai" / "projects" / "empty_proj"
    proj_dir.mkdir(parents=True)

    with patch("ace.changespec.Path.home", return_value=tmp_path):
        result = find_all_changespecs()

    assert result == []


# --- write_changespec_atomic suffix tests ---


def test_write_changespec_atomic_yaml_suffix(tmp_path: Path) -> None:
    """write_changespec_atomic creates temp file with .yaml suffix."""
    yaml_file = str(tmp_path / "proj.yaml")
    content = _make_yaml_content(file_path=yaml_file)

    write_changespec_atomic(yaml_file, content, "test commit")

    # Verify the file was written with correct content
    assert os.path.exists(yaml_file)
    written = Path(yaml_file).read_text()
    assert "test-cl" in written


def test_write_changespec_atomic_gp_suffix(tmp_path: Path) -> None:
    """write_changespec_atomic creates temp file with .gp suffix."""
    gp_file = str(tmp_path / "proj.gp")
    content = _make_gp_content()

    write_changespec_atomic(gp_file, content, "test commit")

    assert os.path.exists(gp_file)
    written = Path(gp_file).read_text()
    assert "test-cl" in written

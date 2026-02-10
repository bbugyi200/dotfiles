"""Tests for xprompt.loader config and file loading functions."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from xprompt.loader import (
    _load_xprompt_from_file,
    _load_xprompts_from_config,
    _parse_yaml_front_matter,
    get_all_xprompts,
)
from xprompt.models import UNSET, InputType, XPrompt

# Tests for _load_xprompt_from_file


def test_load_xprompt_from_file_with_front_matter() -> None:
    """Test loading xprompt file with front matter."""
    content = """---
name: my_prompt
input:
  - name: arg1
    type: string
---
Hello {{ arg1 }}!"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        temp_path = Path(f.name)

    try:
        xprompt = _load_xprompt_from_file(temp_path)

        assert xprompt is not None
        assert xprompt.name == "my_prompt"
        assert len(xprompt.inputs) == 1
        assert xprompt.inputs[0].name == "arg1"
        assert "Hello {{ arg1 }}" in xprompt.content
        assert xprompt.source_path == str(temp_path)
    finally:
        temp_path.unlink()


def test_load_xprompt_from_file_without_front_matter() -> None:
    """Test loading xprompt file without front matter."""
    content = "Just some content without front matter"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        temp_path = Path(f.name)

    try:
        xprompt = _load_xprompt_from_file(temp_path)

        assert xprompt is not None
        # Name should be filename stem
        assert xprompt.name == temp_path.stem
        assert xprompt.inputs == []
        assert xprompt.content == content
    finally:
        temp_path.unlink()


def test_load_xprompt_from_file_name_from_front_matter() -> None:
    """Test that name from front matter overrides filename."""
    content = """---
name: custom_name
---
Content"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        temp_path = Path(f.name)

    try:
        xprompt = _load_xprompt_from_file(temp_path)

        assert xprompt is not None
        assert xprompt.name == "custom_name"
    finally:
        temp_path.unlink()


def test_load_xprompt_from_file_nonexistent() -> None:
    """Test loading nonexistent file returns None."""
    xprompt = _load_xprompt_from_file(Path("/nonexistent/path.md"))
    assert xprompt is None


# Tests for _parse_yaml_front_matter


def test_parse_yaml_front_matter_invalid_yaml() -> None:
    """Test that invalid YAML in front matter returns None and full content."""
    content = """---
invalid: yaml: content: [not closed
---
Body content"""
    front_matter, body = _parse_yaml_front_matter(content)
    assert front_matter is None
    assert body == content


def test_parse_yaml_front_matter_non_dict() -> None:
    """Test that non-dict YAML front matter returns empty dict."""
    content = """---
- just
- a
- list
---
Body content"""
    front_matter, body = _parse_yaml_front_matter(content)
    assert front_matter == {}
    assert body == "Body content"


def test_parse_yaml_front_matter_unclosed() -> None:
    """Test that unclosed front matter returns None and full content."""
    content = """---
name: test
No closing delimiter here"""
    front_matter, body = _parse_yaml_front_matter(content)
    assert front_matter is None
    assert body == content


# Tests for _load_xprompts_from_config


def test_load_xprompts_from_config_basic() -> None:
    """Test loading xprompts from config file."""
    yaml_content = """
xprompts:
  foo: "Foo content"
  bar: "Bar content"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("xprompt.loader._get_config_path", return_value=config_path):
        xprompts = _load_xprompts_from_config()

    assert len(xprompts) == 2
    assert xprompts["foo"].content == "Foo content"
    assert xprompts["bar"].content == "Bar content"
    assert xprompts["foo"].source_path == "config"

    Path(config_path).unlink()


def test_load_xprompts_from_config_structured_with_inputs() -> None:
    """Test loading structured xprompts with input/content from config."""
    yaml_content = """
xprompts:
  simple: "Simple content"
  with_input:
    input: { name: word, count: { type: int, default: 0 } }
    content: "Hello {{ name }}, count={{ count }}"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("xprompt.loader._get_config_path", return_value=config_path):
        xprompts = _load_xprompts_from_config()

    assert len(xprompts) == 2

    # Simple xprompt
    assert xprompts["simple"].content == "Simple content"
    assert xprompts["simple"].inputs == []

    # Structured xprompt with inputs
    assert xprompts["with_input"].content == "Hello {{ name }}, count={{ count }}"
    assert len(xprompts["with_input"].inputs) == 2

    names = [i.name for i in xprompts["with_input"].inputs]
    assert "name" in names
    assert "count" in names

    name_input = next(i for i in xprompts["with_input"].inputs if i.name == "name")
    assert name_input.type == InputType.WORD
    assert name_input.default is UNSET

    count_input = next(i for i in xprompts["with_input"].inputs if i.name == "count")
    assert count_input.type == InputType.INT
    assert count_input.default == 0

    Path(config_path).unlink()


def test_load_xprompts_from_config_structured_content_only() -> None:
    """Test loading structured xprompt with only content field."""
    yaml_content = """
xprompts:
  content_only:
    content: "Just content, no inputs"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("xprompt.loader._get_config_path", return_value=config_path):
        xprompts = _load_xprompts_from_config()

    assert len(xprompts) == 1
    assert xprompts["content_only"].content == "Just content, no inputs"
    assert xprompts["content_only"].inputs == []

    Path(config_path).unlink()


def test_load_xprompts_from_config_missing_file() -> None:
    """Test that missing config file returns empty dict."""
    with patch("xprompt.loader._get_config_path", return_value="/nonexistent/path.yml"):
        xprompts = _load_xprompts_from_config()

    assert xprompts == {}


def test_load_xprompts_from_config_missing_key() -> None:
    """Test that config without xprompts/snippets returns empty dict."""
    yaml_content = """
mentor_profiles:
  - name: test
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("xprompt.loader._get_config_path", return_value=config_path):
        xprompts = _load_xprompts_from_config()

    assert xprompts == {}

    Path(config_path).unlink()


# Tests for get_all_xprompts


def test_get_all_xprompts_merges_sources() -> None:
    """Test that xprompts are merged from all sources."""
    yaml_content = """
xprompts:
  from_config: "Config content"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    # Mock file discovery to return a test xprompt
    file_xprompt = XPrompt(name="from_file", content="File content")

    with (
        patch("xprompt.loader._get_config_path", return_value=config_path),
        patch(
            "xprompt.loader._load_xprompts_from_files",
            return_value={"from_file": file_xprompt},
        ),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
    ):
        xprompts = get_all_xprompts()

    assert "from_config" in xprompts
    assert "from_file" in xprompts

    Path(config_path).unlink()


def test_get_all_xprompts_file_overrides_config() -> None:
    """Test that file-based xprompts override config-based ones."""
    yaml_content = """
xprompts:
  test: "From config"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    file_xprompt = XPrompt(name="test", content="From file")

    with (
        patch("xprompt.loader._get_config_path", return_value=config_path),
        patch(
            "xprompt.loader._load_xprompts_from_files",
            return_value={"test": file_xprompt},
        ),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
    ):
        xprompts = get_all_xprompts()

    # File-based should win
    assert xprompts["test"].content == "From file"

    Path(config_path).unlink()


# Tests for _load_xprompts_from_project


def _load_xprompts_from_project_with_base(
    project: str, base_config_dir: Path
) -> dict[str, XPrompt]:
    """Helper to test project loading with a custom base directory.

    This replicates the logic of _load_xprompts_from_project but allows
    specifying a custom base directory for testing.
    """
    project_dir = base_config_dir / ".config" / "gai" / "xprompts" / project
    if not project_dir.is_dir():
        return {}

    xprompts: dict[str, XPrompt] = {}
    for md_file in project_dir.glob("*.md"):
        if md_file.is_file():
            xprompt = _load_xprompt_from_file(md_file)
            if xprompt:
                namespaced_name = f"{project}/{xprompt.name}"
                xprompts[namespaced_name] = XPrompt(
                    name=namespaced_name,
                    content=xprompt.content,
                    inputs=xprompt.inputs,
                    source_path=xprompt.source_path,
                )
    return xprompts


def test_load_xprompts_from_project_basic() -> None:
    """Test loading xprompts from a project-specific directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir) / ".config" / "gai" / "xprompts" / "testproj"
        project_dir.mkdir(parents=True)

        # Create an xprompt file
        (project_dir / "my_prompt.md").write_text("Project-specific content")

        xprompts = _load_xprompts_from_project_with_base("testproj", Path(tmp_dir))

        assert len(xprompts) == 1
        assert "testproj/my_prompt" in xprompts
        assert xprompts["testproj/my_prompt"].content == "Project-specific content"
        assert xprompts["testproj/my_prompt"].name == "testproj/my_prompt"


def test_load_xprompts_from_project_nonexistent_dir() -> None:
    """Test that nonexistent project directory returns empty dict."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        xprompts = _load_xprompts_from_project_with_base(
            "nonexistent_project", Path(tmp_dir)
        )
        assert xprompts == {}


def test_load_xprompts_from_project_preserves_front_matter() -> None:
    """Test that project xprompts preserve front matter including inputs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir) / ".config" / "gai" / "xprompts" / "myproj"
        project_dir.mkdir(parents=True)

        content = """---
name: custom_name
input:
  - name: arg1
    type: word
---
Hello {{ arg1 }}!"""
        (project_dir / "test_prompt.md").write_text(content)

        xprompts = _load_xprompts_from_project_with_base("myproj", Path(tmp_dir))

        assert len(xprompts) == 1
        # Name should be namespaced (project/name_from_front_matter)
        assert "myproj/custom_name" in xprompts
        xp = xprompts["myproj/custom_name"]
        assert xp.name == "myproj/custom_name"
        assert len(xp.inputs) == 1
        assert xp.inputs[0].name == "arg1"
        assert "Hello {{ arg1 }}" in xp.content


def test_get_all_xprompts_with_project_includes_project_xprompts() -> None:
    """Test that get_all_xprompts with project param includes project xprompts."""
    project_xprompt = XPrompt(name="testproj/proj_prompt", content="Project content")

    with (
        patch("xprompt.loader._get_config_path", return_value="/nonexistent/path.yml"),
        patch("xprompt.loader._load_xprompts_from_files", return_value={}),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
        patch(
            "xprompt.loader._load_xprompts_from_project",
            return_value={"testproj/proj_prompt": project_xprompt},
        ),
    ):
        xprompts = get_all_xprompts(project="testproj")

    assert "testproj/proj_prompt" in xprompts
    assert xprompts["testproj/proj_prompt"].content == "Project content"


def test_get_all_xprompts_without_project_excludes_project_xprompts() -> None:
    """Test that get_all_xprompts without project param doesn't load project xprompts."""
    with (
        patch("xprompt.loader._get_config_path", return_value="/nonexistent/path.yml"),
        patch("xprompt.loader._load_xprompts_from_files", return_value={}),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
        patch("xprompt.loader._load_xprompts_from_project") as mock_load_project,
    ):
        get_all_xprompts()  # No project param

    # Should not have called _load_xprompts_from_project
    mock_load_project.assert_not_called()


def test_get_all_xprompts_file_overrides_project() -> None:
    """Test that file-based xprompts override project xprompts."""
    project_xprompt = XPrompt(name="test", content="From project")
    file_xprompt = XPrompt(name="test", content="From file")

    with (
        patch("xprompt.loader._get_config_path", return_value="/nonexistent/path.yml"),
        patch(
            "xprompt.loader._load_xprompts_from_files",
            return_value={"test": file_xprompt},
        ),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
        patch(
            "xprompt.loader._load_xprompts_from_project",
            return_value={"test": project_xprompt},
        ),
    ):
        xprompts = get_all_xprompts(project="testproj")

    # File-based should win
    assert xprompts["test"].content == "From file"


def test_get_all_xprompts_project_overrides_config() -> None:
    """Test that project xprompts override config xprompts."""
    yaml_content = """
xprompts:
  test: "From config"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    project_xprompt = XPrompt(name="test", content="From project")

    with (
        patch("xprompt.loader._get_config_path", return_value=config_path),
        patch("xprompt.loader._load_xprompts_from_files", return_value={}),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
        patch(
            "xprompt.loader._load_xprompts_from_project",
            return_value={"test": project_xprompt},
        ),
    ):
        xprompts = get_all_xprompts(project="testproj")

    # Project should win over config
    assert xprompts["test"].content == "From project"

    Path(config_path).unlink()

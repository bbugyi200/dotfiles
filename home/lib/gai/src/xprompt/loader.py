"""XPrompt discovery and loading from files and configuration."""

import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .models import InputArg, InputType, XPrompt
from .output_schema import OutputSchema, OutputType


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def _get_gai_package_xprompts_dir() -> Path:
    """Get the path to the internal gai xprompts directory."""
    # This file is in src/xprompt/loader.py
    # xprompts dir is at <package>/xprompts/
    loader_path = Path(__file__).resolve()
    src_dir = loader_path.parent.parent  # src/
    package_dir = src_dir.parent  # gai/
    return package_dir / "xprompts"


def _parse_yaml_front_matter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Parse YAML front matter delimited by --- lines.

    Args:
        content: The full file content.

    Returns:
        Tuple of (front_matter_dict, body_content).
        front_matter_dict is None if no front matter found.
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, content

    # Find the closing ---
    end_index = -1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index == -1:
        # No closing ---, treat as no front matter
        return None, content

    # Extract and parse YAML
    yaml_content = "\n".join(lines[1:end_index])
    try:
        front_matter = yaml.safe_load(yaml_content)
        if not isinstance(front_matter, dict):
            front_matter = {}
    except yaml.YAMLError:
        # Invalid YAML, treat as no front matter
        return None, content

    # Body is everything after the closing ---
    body = "\n".join(lines[end_index + 1 :])
    # Remove leading newline if present (common after front matter)
    if body.startswith("\n"):
        body = body[1:]

    return front_matter, body


def _parse_input_type(type_str: str) -> InputType:
    """Parse an input type string to InputType enum.

    Args:
        type_str: The type string (e.g., "word", "line", "text", "path", "int").

    Returns:
        The corresponding InputType enum value.
    """
    type_map = {
        "word": InputType.WORD,
        "line": InputType.LINE,
        "text": InputType.TEXT,
        "path": InputType.PATH,
        "int": InputType.INT,
        "integer": InputType.INT,
        "bool": InputType.BOOL,
        "boolean": InputType.BOOL,
        "float": InputType.FLOAT,
    }
    return type_map.get(type_str.lower(), InputType.LINE)


def _parse_inputs_from_front_matter(
    input_list: list[dict[str, Any]] | None,
) -> list[InputArg]:
    """Parse input definitions from front matter.

    Args:
        input_list: List of input dicts from YAML front matter.

    Returns:
        List of InputArg objects.
    """
    if not input_list:
        return []

    inputs: list[InputArg] = []
    for item in input_list:
        if not isinstance(item, dict) or "name" not in item:
            continue

        name = str(item["name"])
        type_str = str(item.get("type", "string"))
        default = item.get("default")

        inputs.append(
            InputArg(
                name=name,
                type=_parse_input_type(type_str),
                default=default,
            )
        )

    return inputs


def _parse_output_type(type_str: str) -> OutputType | None:
    """Parse an output type string to OutputType enum.

    Args:
        type_str: The type string (e.g., "yaml_schema").

    Returns:
        The corresponding OutputType enum value, or None if unrecognized.
    """
    type_map = {
        "yaml_schema": OutputType.YAML_SCHEMA,
        "yaml": OutputType.YAML_SCHEMA,  # Alias
    }
    return type_map.get(type_str.lower())


def _parse_output_from_front_matter(
    output_dict: dict[str, Any] | None,
) -> OutputSchema | None:
    """Parse output schema definition from front matter.

    Args:
        output_dict: The output dict from YAML front matter.

    Returns:
        OutputSchema object if valid, None otherwise.
    """
    if not output_dict or not isinstance(output_dict, dict):
        return None

    # Type is required
    type_str = output_dict.get("type")
    if not type_str or not isinstance(type_str, str):
        return None

    output_type = _parse_output_type(type_str)
    if output_type is None:
        return None

    # Validator is optional
    validator = output_dict.get("validator")
    if validator is not None and not isinstance(validator, str):
        validator = None

    # Format instructions are optional
    format_instructions = output_dict.get("format_instructions")
    if format_instructions is not None and not isinstance(format_instructions, str):
        format_instructions = None

    return OutputSchema(
        type=output_type,
        validator=validator,
        format_instructions=format_instructions,
    )


def _load_xprompt_from_file(file_path: Path) -> XPrompt | None:
    """Load a single xprompt from a markdown file.

    Args:
        file_path: Path to the .md file.

    Returns:
        XPrompt object if successfully loaded, None otherwise.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return None

    front_matter, body = _parse_yaml_front_matter(content)

    # Get name from front matter or fallback to filename
    if front_matter and "name" in front_matter:
        name = str(front_matter["name"])
    else:
        name = file_path.stem  # Filename without extension

    # Parse inputs if present
    inputs: list[InputArg] = []
    if front_matter and "input" in front_matter:
        inputs = _parse_inputs_from_front_matter(front_matter["input"])

    # Parse output schema if present
    output: OutputSchema | None = None
    if front_matter and "output" in front_matter:
        output = _parse_output_from_front_matter(front_matter["output"])

    return XPrompt(
        name=name,
        content=body,
        inputs=inputs,
        source_path=str(file_path),
        output=output,
    )


def _get_xprompt_search_paths() -> list[Path]:
    """Get the ordered list of directories to search for xprompt files.

    Priority order (first wins on name conflict):
    1. .xprompts/*.md (CWD, hidden)
    2. xprompts/*.md (CWD, non-hidden)
    3. ~/.xprompts/*.md (home, hidden)
    4. ~/xprompts/*.md (home, non-hidden)
    5. (config is handled separately)
    6. <gai_package>/xprompts/*.md (internal)

    Returns:
        List of directory paths to search, in priority order.
    """
    cwd = Path.cwd()
    home = Path.home()

    paths = [
        cwd / ".xprompts",
        cwd / "xprompts",
        home / ".xprompts",
        home / "xprompts",
    ]

    return paths


def _discover_xprompt_files() -> list[tuple[Path, int]]:
    """Find all xprompt files in search paths with priority info.

    Returns:
        List of (file_path, priority) tuples, where lower priority wins.
    """
    search_paths = _get_xprompt_search_paths()
    results: list[tuple[Path, int]] = []

    for priority, search_dir in enumerate(search_paths):
        if not search_dir.is_dir():
            continue

        for md_file in search_dir.glob("*.md"):
            if md_file.is_file():
                results.append((md_file, priority))

    return results


def _load_xprompts_from_files() -> dict[str, XPrompt]:
    """Load xprompts from file system locations.

    Returns:
        Dictionary mapping xprompt name to XPrompt object.
        Earlier priority sources override later ones.
    """
    discovered = _discover_xprompt_files()

    # Sort by priority (lower is higher priority)
    discovered.sort(key=lambda x: x[1])

    xprompts: dict[str, XPrompt] = {}
    for file_path, _ in discovered:
        xprompt = _load_xprompt_from_file(file_path)
        if xprompt and xprompt.name not in xprompts:
            # First occurrence wins
            xprompts[xprompt.name] = xprompt

    return xprompts


def _load_xprompts_from_config() -> dict[str, XPrompt]:
    """Load xprompts from gai.yml configuration file.

    Supports both 'xprompts' and legacy 'snippets' keys.

    Returns:
        Dictionary mapping xprompt name to XPrompt object.
    """
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        return {}

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    xprompts: dict[str, XPrompt] = {}

    # Check both 'xprompts' and 'snippets' keys (xprompts takes priority)
    for key in ("xprompts", "snippets"):
        if key not in data:
            continue

        config_data = data[key]
        if not isinstance(config_data, dict):
            continue

        for name, content in config_data.items():
            if not isinstance(name, str) or not isinstance(content, str):
                continue

            # Only add if not already present (xprompts overrides snippets)
            if name not in xprompts:
                xprompts[name] = XPrompt(
                    name=name,
                    content=content,
                    inputs=[],  # Config-based xprompts don't have typed inputs
                    source_path="config",
                )

    return xprompts


def _load_xprompts_from_internal() -> dict[str, XPrompt]:
    """Load xprompts from the internal gai package xprompts directory.

    Returns:
        Dictionary mapping xprompt name to XPrompt object.
    """
    internal_dir = _get_gai_package_xprompts_dir()

    if not internal_dir.is_dir():
        return {}

    xprompts: dict[str, XPrompt] = {}
    for md_file in internal_dir.glob("*.md"):
        if md_file.is_file():
            xprompt = _load_xprompt_from_file(md_file)
            if xprompt:
                xprompts[xprompt.name] = xprompt

    return xprompts


def get_all_xprompts() -> dict[str, XPrompt]:
    """Get all xprompts from all sources, respecting priority order.

    Priority order (first wins on name conflict):
    1. .xprompts/*.md (CWD, hidden)
    2. xprompts/*.md (CWD, non-hidden)
    3. ~/.xprompts/*.md (home, hidden)
    4. ~/xprompts/*.md (home, non-hidden)
    5. gai.yml xprompts:/snippets: section
    6. <gai_package>/xprompts/*.md (internal)

    Returns:
        Dictionary mapping xprompt name to XPrompt object.
    """
    # Start with lowest priority and let higher priority override
    all_xprompts: dict[str, XPrompt] = {}

    # 6. Internal xprompts (lowest priority)
    all_xprompts.update(_load_xprompts_from_internal())

    # 5. Config-based xprompts
    config_xprompts = _load_xprompts_from_config()
    all_xprompts.update(config_xprompts)

    # 1-4. File-based xprompts (highest priority) - already sorted
    file_xprompts = _load_xprompts_from_files()
    all_xprompts.update(file_xprompts)

    return all_xprompts


def get_all_snippets() -> dict[str, str]:
    """Legacy compatibility function: get all xprompts as simple name->content dict.

    This is a drop-in replacement for snippet_config.get_all_snippets().

    Returns:
        Dictionary mapping xprompt name to content string.
    """
    xprompts = get_all_xprompts()
    return {name: xp.content for name, xp in xprompts.items()}

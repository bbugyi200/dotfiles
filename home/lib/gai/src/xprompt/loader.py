"""XPrompt discovery and loading from files and configuration."""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]

from .models import InputArg, InputType, OutputSpec, XPrompt

if TYPE_CHECKING:
    from xprompt.workflow_models import Workflow


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def get_gai_package_xprompts_dir() -> Path:
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


def parse_input_type(type_str: str) -> InputType:
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


def _parse_shortform_input_value(value: str | dict[str, Any]) -> tuple[str, Any]:
    """Parse shortform input value into (type, default).

    Args:
        value: Either a type string (e.g., "word") or a dict with 'type' and
            optional 'default' keys (e.g., {"type": "line", "default": ""}).

    Returns:
        Tuple of (type_str, default_value). default_value is None if no default.
    """
    if isinstance(value, dict):
        type_str = str(value.get("type", "line"))
        default = value.get("default")
        return type_str, default

    # Simple string type without default
    return str(value).strip(), None


def parse_shortform_inputs(
    input_dict: Mapping[str, str | dict[str, Any]],
) -> list[InputArg]:
    """Parse shortform input dict to list of InputArg.

    Args:
        input_dict: Dict mapping name to type string or dict with type/default.
            Example: {"diff_path": "path", "bug_flag": {"type": "line", "default": ""}}

    Returns:
        List of InputArg objects.
    """
    inputs: list[InputArg] = []
    for name, value in input_dict.items():
        type_str, default = _parse_shortform_input_value(value)
        inputs.append(
            InputArg(
                name=name,
                type=parse_input_type(type_str),
                default=default,
            )
        )
    return inputs


def _normalize_schema_properties(schema: dict[str, Any]) -> dict[str, Any]:
    """Expand shortform properties in a schema to standard JSON Schema format.

    Converts shortform like {"name": {"type": "word"}} to proper nested format.
    This handles both top-level properties and nested array items.

    Args:
        schema: The schema dict to normalize.

    Returns:
        Normalized schema dict.
    """
    if not isinstance(schema, dict):
        return schema

    result = dict(schema)

    # Handle properties
    if "properties" in result:
        result["properties"] = {
            name: _normalize_schema_properties(prop)
            for name, prop in result["properties"].items()
        }

    # Handle array items
    if "items" in result:
        result["items"] = _normalize_schema_properties(result["items"])

    return result


def _parse_shortform_output(output_data: dict[str, Any] | list[Any]) -> OutputSpec:
    """Convert shortform output syntax to OutputSpec.

    Shortform dict: {field: type} → OutputSpec with json_schema type
    Shortform list: [{field: type}] → OutputSpec with array schema

    Args:
        output_data: Either a dict like {"name": "word", "desc": "text"}
            or a list like [{"name": "word", "desc": {"type": "text", "default": ""}}].

    Returns:
        OutputSpec object.
    """
    if isinstance(output_data, list):
        # Array of objects syntax: [{name: word, desc: {type: text, default: ""}}]
        if not output_data:
            return OutputSpec(type="json_schema", schema={"type": "array", "items": {}})

        item_spec = output_data[0]
        if not isinstance(item_spec, dict):
            return OutputSpec(type="json_schema", schema={"type": "array", "items": {}})

        properties: dict[str, dict[str, str]] = {}
        required: list[str] = []

        for field_name, field_value in item_spec.items():
            type_str, default = _parse_shortform_input_value(field_value)
            properties[field_name] = {"type": type_str}
            # Fields without defaults are required
            if default is None:
                required.append(field_name)

        items_schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            items_schema["required"] = required

        return OutputSpec(
            type="json_schema",
            schema={
                "type": "array",
                "items": items_schema,
            },
        )
    else:
        # Object syntax: {name: word, desc: text}
        properties = {}
        for field_name, field_value in output_data.items():
            type_str, _ = _parse_shortform_input_value(field_value)
            properties[field_name] = {"type": type_str}

        return OutputSpec(
            type="json_schema",
            schema={
                "properties": properties,
            },
        )


def _parse_inputs_from_front_matter(
    input_data: list[dict[str, Any]] | dict[str, str | dict[str, Any]] | None,
) -> list[InputArg]:
    """Parse input definitions from front matter.

    Supports both longform (list of dicts) and shortform (dict) syntax.

    Args:
        input_data: Either a list of input dicts (longform) or a dict (shortform).
            Longform: [{"name": "foo", "type": "word", "default": ""}]
            Shortform: {"foo": "word", "bar": {"type": "line", "default": ""}}

    Returns:
        List of InputArg objects.
    """
    if not input_data:
        return []

    # Handle shortform dict syntax
    if isinstance(input_data, dict):
        return parse_shortform_inputs(input_data)

    # Handle longform list syntax
    inputs: list[InputArg] = []
    for item in input_data:
        if not isinstance(item, dict) or "name" not in item:
            continue

        name = str(item["name"])
        type_str = str(item.get("type", "line"))
        default = item.get("default")

        inputs.append(
            InputArg(
                name=name,
                type=parse_input_type(type_str),
                default=default,
            )
        )

    return inputs


def parse_output_from_front_matter(
    output_data: dict[str, Any] | list[Any] | None,
) -> OutputSpec | None:
    """Parse output specification from front matter.

    Supports both longform and shortform syntax.

    Longform:
        output:
          type: json_schema
          schema:
            properties:
              name: {type: word}

    Shortform (object):
        output: {name: word, desc: text}

    Shortform (array):
        output: [{name: word, desc: text = ""}]

    Args:
        output_data: The output data from YAML front matter.

    Returns:
        OutputSpec object if valid output specification found, None otherwise.
    """
    if not output_data:
        return None

    # Handle shortform list syntax: [{name: word, desc: text}]
    if isinstance(output_data, list):
        return _parse_shortform_output(output_data)

    # Check if this is longform (has 'type' and 'schema' keys) or shortform
    output_type = output_data.get("type")
    schema = output_data.get("schema")

    # Longform: has both 'type' and 'schema' keys, and 'type' is a string like "json_schema"
    if (
        output_type
        and isinstance(output_type, str)
        and schema
        and isinstance(schema, dict)
    ):
        return OutputSpec(type=output_type, schema=schema)

    # Shortform dict: {name: word, desc: text}
    # If 'type' is present but not a known longform type, treat as shortform
    return _parse_shortform_output(output_data)


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

    # Parse output specification if present
    output: OutputSpec | None = None
    if front_matter and "output" in front_matter:
        output = parse_output_from_front_matter(front_matter["output"])

    return XPrompt(
        name=name,
        content=body,
        inputs=inputs,
        source_path=str(file_path),
        output=output,
    )


def get_xprompt_search_paths() -> list[Path]:
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
    search_paths = get_xprompt_search_paths()
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

    Supports both simple string format and structured dict format:

    Simple format:
        xprompts:
          foo: "Content here"

    Structured format (with inputs):
        xprompts:
          bar:
            input: {name: word, count: {type: int, default: 0}}
            content: "Hello {{ name }}, count is {{ count }}"
            output: {result: text}  # optional

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

    config_data = data.get("xprompts")
    if not isinstance(config_data, dict):
        return {}

    for name, value in config_data.items():
        if not isinstance(name, str):
            continue

        if isinstance(value, str):
            # Simple string content (no arguments)
            content = value
            inputs: list[InputArg] = []
            output: OutputSpec | None = None
        elif isinstance(value, dict):
            # Structured xprompt with input/content
            content = value.get("content", "")
            if not isinstance(content, str):
                continue
            inputs = _parse_inputs_from_front_matter(value.get("input"))
            output = parse_output_from_front_matter(value.get("output"))
        else:
            continue

        xprompts[name] = XPrompt(
            name=name,
            content=content,
            inputs=inputs,
            source_path="config",
            output=output,
        )

    return xprompts


def _load_xprompts_from_internal() -> dict[str, XPrompt]:
    """Load xprompts from the internal gai package xprompts directory.

    Returns:
        Dictionary mapping xprompt name to XPrompt object.
    """
    internal_dir = get_gai_package_xprompts_dir()

    if not internal_dir.is_dir():
        return {}

    xprompts: dict[str, XPrompt] = {}
    for md_file in internal_dir.glob("*.md"):
        if md_file.is_file():
            xprompt = _load_xprompt_from_file(md_file)
            if xprompt:
                xprompts[xprompt.name] = xprompt

    return xprompts


def _load_xprompts_from_project(project: str) -> dict[str, XPrompt]:
    """Load xprompts from a project-specific directory.

    Loads xprompts from ~/.config/gai/xprompts/{project}/*.md and namespaces
    them with the project name (e.g., bar.md → foo/bar for project 'foo').

    Args:
        project: The project name to load xprompts for.

    Returns:
        Dictionary mapping namespaced xprompt name to XPrompt object.
        Returns empty dict if directory doesn't exist.
    """
    project_dir = Path.home() / ".config" / "gai" / "xprompts" / project
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
                    output=xprompt.output,
                )
    return xprompts


def get_all_xprompts(project: str | None = None) -> dict[str, XPrompt]:
    """Get all xprompts from all sources, respecting priority order.

    Priority order (first wins on name conflict):
    1. .xprompts/*.md (CWD, hidden)
    2. xprompts/*.md (CWD, non-hidden)
    3. ~/.xprompts/*.md (home, hidden)
    4. ~/xprompts/*.md (home, non-hidden)
    5. ~/.config/gai/xprompts/{project}/*.md (project-specific, if project given)
    6. gai.yml xprompts:/snippets: section
    7. <gai_package>/xprompts/*.md (internal)

    Args:
        project: Optional project name to include project-specific xprompts.

    Returns:
        Dictionary mapping xprompt name to XPrompt object.
    """
    # Start with lowest priority and let higher priority override
    all_xprompts: dict[str, XPrompt] = {}

    # 7. Internal xprompts (lowest priority)
    all_xprompts.update(_load_xprompts_from_internal())

    # 6. Config-based xprompts
    config_xprompts = _load_xprompts_from_config()
    all_xprompts.update(config_xprompts)

    # 5. Project-specific xprompts (if project provided)
    if project:
        project_xprompts = _load_xprompts_from_project(project)
        all_xprompts.update(project_xprompts)

    # 1-4. File-based xprompts (highest priority) - already sorted
    file_xprompts = _load_xprompts_from_files()
    all_xprompts.update(file_xprompts)

    return all_xprompts


def get_all_workflows() -> dict[str, "Workflow"]:
    """Get all workflows from all sources, respecting priority order.

    This is a wrapper around workflow_loader.get_all_workflows() to provide
    a unified interface in the loader module.

    Returns:
        Dictionary mapping workflow name to Workflow object.
    """
    from xprompt.workflow_loader import get_all_workflows as _get_all_workflows

    return _get_all_workflows()


def get_xprompt_or_workflow(
    name: str, project: str | None = None
) -> "XPrompt | Workflow | None":
    """Look up an xprompt or workflow by name.

    Checks xprompts first, then workflows. This allows the same #name(args)
    syntax to work for both.

    Args:
        name: The name to look up.
        project: Optional project name to include project-specific xprompts.

    Returns:
        XPrompt or Workflow object if found, None otherwise.
    """
    # Check xprompts first
    xprompts = get_all_xprompts(project=project)
    if name in xprompts:
        return xprompts[name]

    # Check workflows
    workflows = get_all_workflows()
    if name in workflows:
        return workflows[name]

    return None

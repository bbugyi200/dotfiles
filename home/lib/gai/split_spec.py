"""SplitSpec data structures and parsing for the gai split command."""

from dataclasses import dataclass

import yaml  # type: ignore[import-untyped]


@dataclass
class SplitEntry:
    """Represents a single CL to create during a split."""

    name: str
    description: str
    files: list[str]
    parent: str | None = None


@dataclass
class SplitSpec:
    """Represents the complete split specification."""

    entries: list[SplitEntry]


def parse_split_spec(yaml_content: str) -> SplitSpec:
    """Parse a SplitSpec from YAML content.

    Args:
        yaml_content: The YAML content to parse.

    Returns:
        The parsed SplitSpec.

    Raises:
        ValueError: If the YAML content is invalid.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}") from e

    if not isinstance(data, list):
        raise ValueError("SplitSpec must be a list of entries")

    entries = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Entry {i} must be a dictionary")

        # Required fields
        name = item.get("name")
        if not name:
            raise ValueError(f"Entry {i} missing required 'name' field")
        if not isinstance(name, str):
            raise ValueError(f"Entry {i} 'name' must be a string")

        description = item.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"Entry {i} 'description' must be a string")

        files = item.get("files", [])
        if not isinstance(files, list):
            raise ValueError(f"Entry {i} 'files' must be a list")
        for j, f in enumerate(files):
            if not isinstance(f, str):
                raise ValueError(f"Entry {i} 'files[{j}]' must be a string")

        # Optional fields
        parent = item.get("parent")
        if parent is not None and not isinstance(parent, str):
            raise ValueError(f"Entry {i} 'parent' must be a string")

        entries.append(
            SplitEntry(
                name=name,
                description=description.strip(),
                files=files,
                parent=parent,
            )
        )

    return SplitSpec(entries=entries)


def validate_split_spec(spec: SplitSpec) -> tuple[bool, str | None]:
    """Validate that parent references exist within the spec.

    Args:
        spec: The SplitSpec to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    # Build set of all entry names
    entry_names = {entry.name for entry in spec.entries}

    # Check for duplicate names
    if len(entry_names) != len(spec.entries):
        seen = set()
        for entry in spec.entries:
            if entry.name in seen:
                return (False, f"Duplicate entry name: '{entry.name}'")
            seen.add(entry.name)

    # Check that all parent references are valid
    for entry in spec.entries:
        if entry.parent is not None and entry.parent not in entry_names:
            return (
                False,
                f"Entry '{entry.name}' has invalid parent reference: '{entry.parent}'",
            )

    # Check for cycles
    has_cycle, cycle_entry = _detect_cycle(spec)
    if has_cycle:
        return (False, f"Cycle detected involving entry: '{cycle_entry}'")

    return (True, None)


def _detect_cycle(spec: SplitSpec) -> tuple[bool, str | None]:
    """Detect if there's a cycle in the parent relationships.

    Args:
        spec: The SplitSpec to check.

    Returns:
        Tuple of (has_cycle, entry_name_in_cycle).
    """
    name_to_entry = {entry.name: entry for entry in spec.entries}

    for entry in spec.entries:
        visited: set[str] = set()
        current: SplitEntry | None = entry

        while current is not None:
            if current.name in visited:
                return (True, current.name)
            visited.add(current.name)

            if current.parent is None:
                break
            current = name_to_entry.get(current.parent)

    return (False, None)


def topological_sort_entries(entries: list[SplitEntry]) -> list[SplitEntry]:
    """Sort entries depth-first so parents come before children.

    Args:
        entries: The list of entries to sort.

    Returns:
        The sorted list of entries.
    """
    name_to_entry = {e.name: e for e in entries}
    visited: set[str] = set()
    result: list[SplitEntry] = []

    def visit(entry: SplitEntry) -> None:
        if entry.name in visited:
            return
        # Visit parent first if it exists in the spec
        if entry.parent and entry.parent in name_to_entry:
            visit(name_to_entry[entry.parent])
        visited.add(entry.name)
        result.append(entry)

    # Process all roots first (entries without parents or with external parents)
    for entry in entries:
        if entry.parent is None or entry.parent not in name_to_entry:
            visit(entry)

    # Then process any remaining entries
    for entry in entries:
        visit(entry)

    return result


def format_split_spec_as_markdown(spec: SplitSpec) -> str:
    """Format a SplitSpec as markdown for display.

    Args:
        spec: The SplitSpec to format.

    Returns:
        Markdown-formatted string.
    """
    lines = []
    sorted_entries = topological_sort_entries(spec.entries)

    for i, entry in enumerate(sorted_entries, 1):
        lines.append(f"### {i}. {entry.name}")
        if entry.parent:
            lines.append(f"**Parent:** {entry.parent}")
        lines.append("")
        lines.append("**Description:**")
        lines.append(entry.description if entry.description else "(none)")
        lines.append("")
        lines.append("**Files:**")
        for f in entry.files:
            lines.append(f"- `{f}`")
        lines.append("")

    return "\n".join(lines)

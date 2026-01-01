"""Evaluator for query expressions against ChangeSpecs."""

import re
from pathlib import Path

from ..changespec import ChangeSpec, has_any_status_suffix
from .types import AndExpr, NotExpr, OrExpr, PropertyMatch, QueryExpr, StringMatch

# Pattern that indicates a running agent in searchable text
# Matches "- (@)" (no message) or "- (@: msg)" (with message)
RUNNING_AGENT_MARKER = "- (@"

# Pattern that indicates a running process in searchable text
# Matches "- ($: PID)" (hook subprocess with PID)
RUNNING_PROCESS_MARKER = "- ($: "


def _get_searchable_text(changespec: ChangeSpec) -> str:
    """Extract all searchable text from a ChangeSpec.

    Searches against:
    - name
    - description
    - status (base status without suffixes)
    - project basename (from file_path)
    - parent (if present)
    - cl (if present)
    - kickstart (if present)
    - history notes (if present)
    - hook commands (if present)

    Args:
        changespec: The ChangeSpec to extract text from.

    Returns:
        Combined text for searching (newline-separated).
    """
    parts: list[str] = [
        changespec.name,
        changespec.description,
        changespec.status,
    ]

    # Add project basename (e.g., "myproject" from "~/.gai/projects/myproject/myproject.gp")
    project_path = Path(changespec.file_path)
    parts.append(project_path.parent.name)

    if changespec.parent:
        parts.append(changespec.parent)
    if changespec.cl:
        parts.append(changespec.cl)
    if changespec.kickstart:
        parts.append(changespec.kickstart)

    # Add history notes and suffixes
    if changespec.commits:
        for entry in changespec.commits:
            parts.append(entry.note)
            # Include suffix with prefix for searching (e.g., "(!: NEW PROPOSAL)")
            if entry.suffix:
                if entry.suffix_type == "error":
                    parts.append(f"(!: {entry.suffix})")
                else:
                    parts.append(f"({entry.suffix})")

    # Add hook commands and status line suffixes
    if changespec.hooks:
        for hook in changespec.hooks:
            parts.append(hook.display_command)
            # Include status line suffixes for searching
            if hook.status_lines:
                for sl in hook.status_lines:
                    # Handle running_agent suffix (including empty suffix for RUNNING status)
                    if sl.suffix_type == "running_agent":
                        if sl.suffix:
                            parts.append(f"- (@: {sl.suffix})")
                        else:
                            parts.append("- (@)")
                    # Handle running_process suffix (PID for RUNNING hooks)
                    elif sl.suffix_type == "running_process":
                        parts.append(f"- ($: {sl.suffix})")
                    # Handle killed_process suffix (PID for killed hooks)
                    elif sl.suffix_type == "killed_process":
                        parts.append(f"- (~$: {sl.suffix})")
                    elif sl.suffix:
                        if sl.suffix_type == "error":
                            parts.append(f"(!: {sl.suffix})")
                        else:
                            parts.append(f"({sl.suffix})")

    # Add comment entries and suffixes
    if changespec.comments:
        for comment in changespec.comments:
            parts.append(comment.reviewer)
            parts.append(comment.file_path)
            # Handle running_agent suffix (CRS running)
            if comment.suffix_type == "running_agent":
                if comment.suffix:
                    parts.append(f"- (@: {comment.suffix})")
                else:
                    parts.append("- (@)")
            # Handle running_process suffix (for consistency)
            elif comment.suffix_type == "running_process":
                parts.append(f"- ($: {comment.suffix})")
            # Handle killed_process suffix (for consistency)
            elif comment.suffix_type == "killed_process":
                parts.append(f"- (~$: {comment.suffix})")
            elif comment.suffix:
                if comment.suffix_type == "error":
                    parts.append(f"(!: {comment.suffix})")
                else:
                    parts.append(f"({comment.suffix})")

    return "\n".join(parts)


def _match_string(text: str, match: StringMatch) -> bool:
    """Check if text contains the string match.

    Args:
        text: The text to search in.
        match: The StringMatch to check.

    Returns:
        True if the text contains the match value.
    """
    if match.case_sensitive:
        return match.value in text
    return match.value.lower() in text.lower()


def _get_base_status(status: str) -> str:
    """Get base status without workspace suffix or READY TO MAIL suffix.

    Args:
        status: The full status string (e.g., "Drafted (fig_1)" or "Drafted - (!: READY TO MAIL)").

    Returns:
        The base status value (e.g., "Drafted").
    """
    # Strip workspace suffix: " (<project>_<N>)" at end
    status = re.sub(r" \([a-zA-Z0-9_-]+_\d+\)$", "", status)
    # Strip READY TO MAIL suffix
    status = re.sub(r" - \(!\: READY TO MAIL\)$", "", status)
    return status.strip()


def _match_status(prop: PropertyMatch, changespec: ChangeSpec) -> bool:
    """Match against ChangeSpec STATUS field.

    Args:
        prop: The PropertyMatch with key="status".
        changespec: The ChangeSpec to check.

    Returns:
        True if the base status matches (case-insensitive).
    """
    base_status = _get_base_status(changespec.status)
    return base_status.lower() == prop.value.lower()


def _match_project(prop: PropertyMatch, changespec: ChangeSpec) -> bool:
    """Match against ChangeSpec project (from file_path).

    Args:
        prop: The PropertyMatch with key="project".
        changespec: The ChangeSpec to check.

    Returns:
        True if the project basename matches (case-insensitive).
    """
    project_path = Path(changespec.file_path)
    project_name = project_path.parent.name
    return project_name.lower() == prop.value.lower()


def _match_ancestor(
    prop: PropertyMatch,
    changespec: ChangeSpec,
    all_changespecs: list[ChangeSpec] | None,
) -> bool:
    """Match if ChangeSpec name or parent chain includes the ancestor value.

    Args:
        prop: The PropertyMatch with key="ancestor".
        changespec: The ChangeSpec to check.
        all_changespecs: List of all ChangeSpecs for parent chain lookup.

    Returns:
        True if the ChangeSpec's name matches the ancestor value, or if any
        parent in the chain (recursively) matches. Returns False if
        all_changespecs is None.
    """
    if all_changespecs is None:
        return False

    ancestor_value = prop.value.lower()

    # Build name -> ChangeSpec map for efficient lookup
    name_map: dict[str, ChangeSpec] = {}
    for cs in all_changespecs:
        name_map[cs.name.lower()] = cs

    # Check if this ChangeSpec or any ancestor matches
    visited: set[str] = set()

    def _has_ancestor(cs: ChangeSpec) -> bool:
        """Recursively check if ChangeSpec has the ancestor."""
        cs_name_lower = cs.name.lower()

        # Cycle detection
        if cs_name_lower in visited:
            return False
        visited.add(cs_name_lower)

        # Check if this ChangeSpec's name matches
        if cs_name_lower == ancestor_value:
            return True

        # Check if parent matches
        if cs.parent:
            parent_lower = cs.parent.lower()
            if parent_lower == ancestor_value:
                return True
            # Recursively check parent's ancestors
            if parent_lower in name_map:
                return _has_ancestor(name_map[parent_lower])

        return False

    return _has_ancestor(changespec)


def _match_property(
    prop: PropertyMatch,
    changespec: ChangeSpec,
    all_changespecs: list[ChangeSpec] | None,
) -> bool:
    """Match a property filter against a ChangeSpec.

    Args:
        prop: The PropertyMatch to evaluate.
        changespec: The ChangeSpec to check.
        all_changespecs: List of all ChangeSpecs (required for ancestor matching).

    Returns:
        True if the property matches.
    """
    if prop.key == "status":
        return _match_status(prop, changespec)
    elif prop.key == "project":
        return _match_project(prop, changespec)
    elif prop.key == "ancestor":
        return _match_ancestor(prop, changespec, all_changespecs)
    else:
        # Unknown property key - should not happen with proper tokenization
        return False


def _evaluate(
    expr: QueryExpr,
    text: str,
    changespec: ChangeSpec,
    all_changespecs: list[ChangeSpec] | None = None,
) -> bool:
    """Recursively evaluate an expression against text.

    Args:
        expr: The query expression to evaluate.
        text: The text to match against.
        changespec: The ChangeSpec being evaluated (for special handling).
        all_changespecs: List of all ChangeSpecs (required for ancestor matching).

    Returns:
        True if the expression matches the text.

    Raises:
        TypeError: If the expression type is unknown.
    """
    if isinstance(expr, StringMatch):
        # Special handling for error suffix shorthand (!!!)
        if expr.is_error_suffix:
            return has_any_status_suffix(changespec)
        # Special handling for running agent shorthand (@@@)
        # Simply check for "- (@" marker in the searchable text
        if expr.is_running_agent:
            return RUNNING_AGENT_MARKER in text
        # Special handling for running process shorthand ($$$)
        # Simply check for "- ($: " marker in the searchable text
        if expr.is_running_process:
            return RUNNING_PROCESS_MARKER in text
        return _match_string(text, expr)
    elif isinstance(expr, PropertyMatch):
        return _match_property(expr, changespec, all_changespecs)
    elif isinstance(expr, NotExpr):
        return not _evaluate(expr.operand, text, changespec, all_changespecs)
    elif isinstance(expr, AndExpr):
        return all(
            _evaluate(op, text, changespec, all_changespecs) for op in expr.operands
        )
    elif isinstance(expr, OrExpr):
        return any(
            _evaluate(op, text, changespec, all_changespecs) for op in expr.operands
        )
    else:
        raise TypeError(f"Unknown expression type: {type(expr)}")


def evaluate_query(
    query: QueryExpr,
    changespec: ChangeSpec,
    all_changespecs: list[ChangeSpec] | None = None,
) -> bool:
    """Evaluate a query expression against a ChangeSpec.

    Args:
        query: The parsed query expression.
        changespec: The ChangeSpec to evaluate against.
        all_changespecs: List of all ChangeSpecs. Required for ancestor:
            property filter matching. If None, ancestor filters return False.

    Returns:
        True if the ChangeSpec matches the query, False otherwise.

    Examples:
        >>> from .parser import parse_query
        >>> query = parse_query('"feature"')
        >>> cs = ChangeSpec(name="my_feature", ...)
        >>> evaluate_query(query, cs)
        True
    """
    searchable_text = _get_searchable_text(changespec)
    return _evaluate(query, searchable_text, changespec, all_changespecs)

"""Evaluator for query expressions against ChangeSpecs."""

from pathlib import Path

from ..changespec import ChangeSpec, has_any_error_suffix, has_any_status_suffix
from .types import AndExpr, NotExpr, OrExpr, QueryExpr, StringMatch


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
    if changespec.history:
        for entry in changespec.history:
            parts.append(entry.note)
            # Include suffix with prefix for searching (e.g., "(!: NEW PROPOSAL)")
            if entry.suffix:
                if entry.suffix_type == "error":
                    parts.append(f"(!: {entry.suffix})")
                elif entry.suffix_type == "acknowledged":
                    parts.append(f"(~: {entry.suffix})")
                else:
                    parts.append(f"({entry.suffix})")

    # Add hook commands and status line suffixes
    if changespec.hooks:
        for hook in changespec.hooks:
            parts.append(hook.display_command)
            # Include status line suffixes for searching
            if hook.status_lines:
                for sl in hook.status_lines:
                    if sl.suffix:
                        if sl.suffix_type == "error":
                            parts.append(f"(!: {sl.suffix})")
                        elif sl.suffix_type == "acknowledged":
                            parts.append(f"(~: {sl.suffix})")
                        else:
                            parts.append(f"({sl.suffix})")

    # Add comment entries and suffixes
    if changespec.comments:
        for comment in changespec.comments:
            parts.append(comment.reviewer)
            parts.append(comment.file_path)
            if comment.suffix:
                if comment.suffix_type == "error":
                    parts.append(f"(!: {comment.suffix})")
                elif comment.suffix_type == "acknowledged":
                    parts.append(f"(~: {comment.suffix})")
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


def _evaluate(expr: QueryExpr, text: str, changespec: ChangeSpec) -> bool:
    """Recursively evaluate an expression against text.

    Args:
        expr: The query expression to evaluate.
        text: The text to match against.
        changespec: The ChangeSpec being evaluated (for special handling).

    Returns:
        True if the expression matches the text.

    Raises:
        TypeError: If the expression type is unknown.
    """
    if isinstance(expr, StringMatch):
        # Special handling for error suffix shorthand (!!!)
        if expr.is_error_suffix:
            return has_any_error_suffix(changespec)
        # Special handling for no status suffix shorthand (!!)
        if expr.is_no_status_suffix:
            return not has_any_status_suffix(changespec)
        return _match_string(text, expr)
    elif isinstance(expr, NotExpr):
        return not _evaluate(expr.operand, text, changespec)
    elif isinstance(expr, AndExpr):
        return all(_evaluate(op, text, changespec) for op in expr.operands)
    elif isinstance(expr, OrExpr):
        return any(_evaluate(op, text, changespec) for op in expr.operands)
    else:
        raise TypeError(f"Unknown expression type: {type(expr)}")


def evaluate_query(query: QueryExpr, changespec: ChangeSpec) -> bool:
    """Evaluate a query expression against a ChangeSpec.

    Args:
        query: The parsed query expression.
        changespec: The ChangeSpec to evaluate against.

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
    return _evaluate(query, searchable_text, changespec)

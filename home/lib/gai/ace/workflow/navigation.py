"""Navigation helpers for the work workflow."""

from ..changespec import ChangeSpec, has_ready_to_mail_suffix
from ..operations import get_available_workflows


def compute_default_option(current_idx: int, total_count: int, direction: str) -> str:
    """Compute the default navigation option.

    Args:
        current_idx: Current index in changespecs list
        total_count: Total number of changespecs
        direction: Current navigation direction ("j" or "k")

    Returns:
        Default option string ("j", "k", or "q")
    """
    is_first = current_idx == 0
    is_last = current_idx == total_count - 1
    is_only_one = total_count == 1

    if is_only_one:
        # Only one ChangeSpec: default to quit
        return "q"
    elif is_last:
        # At the last ChangeSpec: default to quit
        return "q"
    elif is_first and direction == "k":
        # At first ChangeSpec after going backward: reset direction to forward
        return "j"
    elif direction == "k":
        # Going backward: default to prev
        return "k"
    else:
        # Default case: default to next
        return "j"


def _make_sort_key(key: str) -> tuple[str, bool, int]:
    """Create a sort key for alphabetical ordering.

    Returns (lowercase_letter, is_uppercase, number_suffix) tuple.
    Non-letter characters (like "/") sort after all letters.
    """
    base_char = key[0]
    # Handle non-letter characters (like "/")
    if not base_char.isalpha():
        # Sort special chars after letters (z + 1)
        return (chr(ord("z") + 1), False, 0)
    is_upper = base_char.isupper()
    # Extract number suffix if present (e.g., "r1" -> 1, "r2" -> 2)
    num_suffix = 0
    if len(key) > 1 and key[1:].isdigit():
        num_suffix = int(key[1:])
    return (base_char.lower(), is_upper, num_suffix)


def _format_option(key: str, label: str, is_default: bool) -> str:
    """Format an option for display."""
    if is_default:
        return f"[black on green] → {key} ({label}) [/black on green]"
    return f"[cyan]{key}[/cyan] ({label})"


def _get_workflow_label(name: str) -> str:
    """Get the display label for a workflow name."""
    return name


def build_navigation_options(
    current_idx: int,
    total_count: int,
    changespec: ChangeSpec,
    default_option: str,
) -> list[str]:
    """Build the list of navigation option strings for display.

    Options are sorted alphabetically (case-insensitive, lowercase before uppercase).

    Args:
        current_idx: Current index in changespecs list
        total_count: Total number of changespecs
        changespec: Current ChangeSpec
        default_option: The default option

    Returns:
        List of formatted option strings
    """
    # Collect options as (sort_key, formatted_text) tuples
    # Sort key format: (lowercase_letter, is_uppercase, number_suffix)
    # This ensures case-insensitive sort with lowercase before uppercase
    options_with_keys: list[tuple[tuple[str, bool, int], str]] = []

    # Only show accept option if there are proposed entries
    if changespec.commits and any(e.is_proposed for e in changespec.commits):
        options_with_keys.append(
            (_make_sort_key("a"), _format_option("a", "accept", False))
        )

    # Only show diff option if CL is set
    if changespec.cl is not None:
        options_with_keys.append(
            (_make_sort_key("d"), _format_option("d", "diff", False))
        )

    # Only show findreviewers option if READY TO MAIL suffix is present
    if has_ready_to_mail_suffix(changespec.status):
        options_with_keys.append(
            (_make_sort_key("f"), _format_option("f", "findreviewers", False))
        )

    # Only show mail option if READY TO MAIL suffix is present
    if has_ready_to_mail_suffix(changespec.status):
        options_with_keys.append(
            (_make_sort_key("m"), _format_option("m", "mail", False))
        )

    # Navigation: next
    if current_idx < total_count - 1:
        options_with_keys.append(
            (_make_sort_key("j"), _format_option("j", "next", default_option == "j"))
        )

    # Navigation: prev
    if current_idx > 0:
        options_with_keys.append(
            (_make_sort_key("k"), _format_option("k", "prev", default_option == "k"))
        )

    # Quit option
    options_with_keys.append(
        (_make_sort_key("q"), _format_option("q", "quit", default_option == "q"))
    )

    # Show run options for eligible ChangeSpecs
    # Use numbered keys (r1, r2, etc.) if there are multiple workflows
    workflows = get_available_workflows(changespec)
    if len(workflows) == 1:
        label = _get_workflow_label(workflows[0])
        options_with_keys.append(
            (_make_sort_key("r"), _format_option("r", f"run {label}", False))
        )
    elif len(workflows) > 1:
        for i, workflow_name in enumerate(workflows, start=1):
            key = f"r{i}"
            label = _get_workflow_label(workflow_name)
            options_with_keys.append(
                (
                    _make_sort_key(key),
                    _format_option(key, f"run {label}", False),
                )
            )

    # Run query option (uppercase R)
    options_with_keys.append(
        (_make_sort_key("R"), _format_option("R", "run query", False))
    )

    # Only show status change option if not blocked
    # Status change is always available
    options_with_keys.append(
        (_make_sort_key("s"), _format_option("s", "status", False))
    )

    # Show edit hooks option
    options_with_keys.append(
        (_make_sort_key("h"), _format_option("h", "edit hooks", False))
    )

    # View files option is always available
    options_with_keys.append((_make_sort_key("v"), _format_option("v", "view", False)))

    # Refresh option is always available - rescans project files
    options_with_keys.append(
        (_make_sort_key("y"), _format_option("y", "refresh", False))
    )

    # Edit query option (/) - always available
    options_with_keys.append(
        (_make_sort_key("/"), _format_option("/", "edit query", False))
    )

    # Sort by the sort key and return just the formatted strings
    options_with_keys.sort(key=lambda x: x[0])
    return [opt[1] for opt in options_with_keys]

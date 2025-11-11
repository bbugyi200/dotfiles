"""Mail operations for the work subcommand."""

import os
import re
import subprocess
import sys

from rich.console import Console
from status_state_machine import transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs


def _has_valid_parent(changespec: ChangeSpec) -> tuple[bool, ChangeSpec | None]:
    """Check if the ChangeSpec has a valid parent (not "Submitted").

    Args:
        changespec: The ChangeSpec to check

    Returns:
        Tuple of (has_valid_parent, parent_changespec)
    """
    if not changespec.parent or changespec.parent == "None":
        return False, None

    # Find the parent ChangeSpec
    all_changespecs = find_all_changespecs()
    for cs in all_changespecs:
        if cs.name == changespec.parent:
            # Parent is valid if its status is NOT "Submitted"
            return cs.status != "Submitted", cs

    # Parent not found
    return False, None


def _get_cl_description(target_dir: str, console: Console) -> tuple[bool, str | None]:
    """Get the current CL description using hdesc command.

    Args:
        target_dir: Directory to run hdesc in
        console: Rich console for output

    Returns:
        Tuple of (success, description or None)
    """
    try:
        result = subprocess.run(
            ["hdesc"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        error_msg = f"hdesc failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        console.print(f"[red]{error_msg}[/red]")
        return False, None
    except FileNotFoundError:
        console.print("[red]hdesc command not found[/red]")
        return False, None
    except Exception as e:
        console.print(f"[red]Unexpected error running hdesc: {str(e)}[/red]")
        return False, None


def _get_branch_number(target_dir: str, console: Console) -> tuple[bool, str | None]:
    """Get the CL branch number using branch_number command.

    Args:
        target_dir: Directory to run branch_number in
        console: Rich console for output

    Returns:
        Tuple of (success, branch_number or None)
    """
    try:
        result = subprocess.run(
            ["branch_number"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        branch_number = result.stdout.strip()
        if not branch_number or not branch_number.isdigit():
            console.print(
                f"[red]Error: branch_number returned invalid value: {branch_number}[/red]"
            )
            return False, None
        return True, branch_number
    except subprocess.CalledProcessError as e:
        error_msg = f"branch_number failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        console.print(f"[red]{error_msg}[/red]")
        return False, None
    except FileNotFoundError:
        console.print("[red]branch_number command not found[/red]")
        return False, None
    except Exception as e:
        console.print(f"[red]Unexpected error running branch_number: {str(e)}[/red]")
        return False, None


def _modify_description_for_mailing(
    description: str,
    reviewers: list[str],
    has_valid_parent: bool,
    parent_branch_number: str | None,
) -> str:
    """Modify CL description for mailing based on number of reviewers and parent validity.

    Args:
        description: Original CL description
        reviewers: List of 1 or 2 reviewers
        has_valid_parent: Whether the ChangeSpec has a valid parent
        parent_branch_number: Branch number of parent CL (if has_valid_parent is True)

    Returns:
        Modified description
    """
    # Find all tags (lines starting with uppercase words followed by colon)
    # Tags are things like "Bug:", "Test:", etc.
    lines = description.split("\n")
    tag_pattern = re.compile(r"^[A-Z][A-Za-z\s]*:")

    # Find the index where tags start (or end of content if no tags)
    tags_start_idx = len(lines)
    for idx, line in enumerate(lines):
        if tag_pattern.match(line.strip()):
            tags_start_idx = idx
            break

    # Split into content (before tags) and tags (from tags onward)
    content_lines = lines[:tags_start_idx]
    tag_lines = lines[tags_start_idx:]

    # Remove trailing blank lines from content
    while content_lines and content_lines[-1].strip() == "":
        content_lines.pop()

    # Process based on scenario
    num_reviewers = len(reviewers)

    if num_reviewers == 1 and not has_valid_parent:
        # Scenario 1: Replace R=startblock with R=<reviewer>
        modified_description = description.replace("R=startblock", f"R={reviewers[0]}")
        return modified_description

    elif num_reviewers == 1 and has_valid_parent:
        # Scenario 2: Replace R=startblock with R=<reviewer>,startblock and add section
        modified_lines = "\n".join(content_lines)
        modified_lines = modified_lines.replace(
            "R=startblock", f"R={reviewers[0]},startblock"
        )

        # Add startblock section
        startblock_section = f"""
### Startblock Conditions

```
Startblock:
    # STAGE 1: wait for LGTM on parent CL
    cl/{parent_branch_number} has LGTM
    all comments on cl/{parent_branch_number} are resolved
    # STAGE 2: add reviewer
    and then
    remember
    add reviewer {reviewers[0]}
```"""

        # Reconstruct description
        result_lines = [modified_lines, "", startblock_section]
        if tag_lines:
            result_lines.extend(["", ""] + tag_lines)
        return "\n".join(result_lines)

    elif num_reviewers == 2 and not has_valid_parent:
        # Scenario 3: Replace R=startblock with R=<reviewer1>,startblock and add section
        modified_lines = "\n".join(content_lines)
        modified_lines = modified_lines.replace(
            "R=startblock", f"R={reviewers[0]},startblock"
        )

        # Add startblock section
        startblock_section = f"""
### Startblock Conditions

```
Startblock:
    # STAGE 1: wait for LGTM from teammate
    has LGTM from {reviewers[0]}
    all comments are resolved
    # STAGE 2: add OWNER as reviewer
    and then
    remember
    add reviewer {reviewers[1]}
```"""

        # Reconstruct description
        result_lines = [modified_lines, "", startblock_section]
        if tag_lines:
            result_lines.extend(["", ""] + tag_lines)
        return "\n".join(result_lines)

    else:  # num_reviewers == 2 and has_valid_parent
        # Scenario 4: Add startblock section with 3 stages
        startblock_section = f"""
### Startblock Conditions

```
Startblock:
    # STAGE 1: wait for LGTM on parent CL
    cl/{parent_branch_number} has LGTM
    all comments on cl/{parent_branch_number} are resolved
    # STAGE 2: add teammate as reviewer + wait for LGTM
    and then
    add reviewer {reviewers[0]}
    has LGTM from {reviewers[0]}
    all comments are resolved
    # STAGE 3: add OWNER as reviewer
    and then
    remember
    add reviewer {reviewers[1]}
```"""

        # Reconstruct description
        result_lines = content_lines + ["", startblock_section]
        if tag_lines:
            result_lines.extend(["", ""] + tag_lines)
        return "\n".join(result_lines)


def handle_mail(changespec: ChangeSpec, console: Console) -> bool:
    """Handle mailing a CL with startblock configuration.

    Args:
        changespec: The ChangeSpec to mail
        console: Rich console for output

    Returns:
        True if mailing succeeded, False otherwise
    """
    # Get target directory
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir:
        console.print(
            "[red]Error: GOOG_CLOUD_DIR environment variable is not set[/red]"
        )
        return False
    if not goog_src_dir_base:
        console.print(
            "[red]Error: GOOG_SRC_DIR_BASE environment variable is not set[/red]"
        )
        return False

    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Prompt for reviewers
    console.print("\n[cyan]Enter reviewers (1 or 2, space-separated):[/cyan] ", end="")
    try:
        reviewers_input = input().strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Aborted[/yellow]")
        return False

    reviewers = reviewers_input.split()
    if len(reviewers) not in [1, 2]:
        console.print(
            "[red]Error: Must provide exactly 1 or 2 reviewers (space-separated)[/red]"
        )
        return False

    # Get current CL description
    console.print("[cyan]Getting CL description...[/cyan]")
    success, description = _get_cl_description(target_dir, console)
    if not success or not description:
        return False

    # Check if parent is valid
    has_valid_parent_flag, parent_cs = _has_valid_parent(changespec)
    parent_branch_number = None

    if has_valid_parent_flag and parent_cs:
        # Get parent's branch number
        console.print(
            f"[cyan]Getting parent CL branch number for {parent_cs.name}...[/cyan]"
        )

        # We need to temporarily update to the parent to get its branch number
        # Save current branch name
        current_branch = changespec.name

        try:
            # Update to parent branch
            subprocess.run(
                ["bb_hg_update", parent_cs.name],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            # Get parent's branch number
            success, parent_branch_number = _get_branch_number(target_dir, console)
            if not success:
                console.print("[red]Error: Could not get parent branch number[/red]")
                # Try to restore current branch
                subprocess.run(
                    ["bb_hg_update", current_branch],
                    cwd=target_dir,
                    capture_output=True,
                    text=True,
                )
                return False

        except subprocess.CalledProcessError as e:
            console.print(
                f"[red]Error updating to parent branch (exit code {e.returncode})[/red]"
            )
            return False
        finally:
            # Always try to restore current branch
            try:
                subprocess.run(
                    ["bb_hg_update", current_branch],
                    cwd=target_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError:
                console.print(
                    f"[yellow]Warning: Could not restore to branch {current_branch}[/yellow]"
                )

    # Modify description
    console.print("[cyan]Modifying CL description for mailing...[/cyan]")
    modified_description = _modify_description_for_mailing(
        description, reviewers, has_valid_parent_flag, parent_branch_number
    )

    # Copy modified description to clipboard
    console.print("[cyan]Copying modified CL description to clipboard...[/cyan]")

    # Determine clipboard command based on platform
    if sys.platform == "darwin":
        clipboard_cmd = ["pbcopy"]
    elif sys.platform.startswith("linux"):
        clipboard_cmd = ["xclip", "-selection", "clipboard"]
    else:
        console.print(
            f"[red]FATAL: Unsupported platform for clipboard: {sys.platform}[/red]"
        )
        console.print("[red]Aborting gai work...[/red]")
        sys.exit(1)

    try:
        subprocess.run(
            clipboard_cmd,
            input=modified_description,
            text=True,
            check=True,
        )
        console.print("[green]✓ Modified CL description copied to clipboard![/green]")
    except subprocess.CalledProcessError as e:
        console.print(
            f"[red]FATAL: {clipboard_cmd[0]} failed (exit code {e.returncode})[/red]"
        )
        console.print("[red]Aborting gai work...[/red]")
        sys.exit(1)
    except FileNotFoundError:
        console.print(f"[red]FATAL: {clipboard_cmd[0]} command not found[/red]")
        console.print("[red]Aborting gai work...[/red]")
        sys.exit(1)

    # Update CL description using bb_hg_reword (opens nvim for editing)
    console.print(
        "[cyan]Opening nvim to edit CL description with bb_hg_reword...[/cyan]"
    )
    try:
        subprocess.run(
            ["bb_hg_reword"],
            cwd=target_dir,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        console.print(
            f"[red]FATAL: bb_hg_reword failed (exit code {e.returncode})[/red]"
        )
        console.print("[red]Aborting gai work...[/red]")
        sys.exit(1)
    except FileNotFoundError:
        console.print("[red]FATAL: bb_hg_reword command not found[/red]")
        console.print("[red]Aborting gai work...[/red]")
        sys.exit(1)

    # Prompt user before mailing
    console.print("\n[cyan]Do you want to mail the CL now? (y/n):[/cyan] ", end="")
    try:
        mail_response = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Aborted[/yellow]")
        return False

    if mail_response not in ["y", "yes"]:
        console.print("[yellow]Skipping mail step[/yellow]")
        return False

    # Mail the CL
    console.print(f"[cyan]Mailing CL with: hg mail -r {changespec.name}[/cyan]")
    try:
        subprocess.run(
            ["hg", "mail", "-r", changespec.name],
            cwd=target_dir,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        error_msg = f"hg mail failed (exit code {e.returncode})"
        console.print(f"[red]{error_msg}[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]hg command not found[/red]")
        return False

    console.print("[green]CL mailed successfully![/green]")

    # Update status to "Mailed"
    console.print("[cyan]Updating status to 'Mailed'...[/cyan]")
    status_success, old_status, status_error = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        "Mailed",
        validate=True,
    )
    if status_success:
        console.print(
            f"[green]Status updated: {old_status if old_status else 'Pre-Mailed'} → Mailed[/green]"
        )
        return True
    else:
        console.print(
            f"[yellow]Warning: CL was mailed but status update failed: {status_error if status_error else 'Unknown error'}[/yellow]"
        )
        return True  # Still return True since mailing succeeded

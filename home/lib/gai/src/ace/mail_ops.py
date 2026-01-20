"""Mail operations for the work subcommand."""

import os
import re
import subprocess
import sys
from dataclasses import dataclass

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import get_workspace_directory
from status_state_machine import (
    remove_ready_to_mail_suffix,
    transition_changespec_status,
)

from .changespec import ChangeSpec, find_all_changespecs


@dataclass
class MailPrepResult:
    """Result of mail preparation (before actual mailing).

    Attributes:
        should_mail: True if the user confirmed they want to mail the CL.
        target_dir: The workspace directory for the CL.
    """

    should_mail: bool
    target_dir: str


def _has_valid_parent(changespec: ChangeSpec) -> tuple[bool, ChangeSpec | None]:
    """Check if the ChangeSpec has a valid parent (not "Submitted").

    Args:
        changespec: The ChangeSpec to check

    Returns:
        Tuple of (has_valid_parent, parent_changespec)
    """
    if not changespec.parent:
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


def _run_findreviewers(target_dir: str, console: Console) -> bool:
    """Run p4 findreviewers command and display output.

    Args:
        target_dir: Directory to run commands in
        console: Rich console for output

    Returns:
        True if successful, False if an error occurred
    """
    # Get the CL number using branch_number command
    success, cl_number = _get_branch_number(target_dir, console)
    if not success or not cl_number:
        return False

    # Run p4 findreviewers command
    console.print("[cyan]Running p4 findreviewers...[/cyan]\n")
    try:
        result = subprocess.run(
            ["p4", "findreviewers", "-c", cl_number],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        # Display the output
        if result.stdout:
            console.print(result.stdout)
        else:
            console.print("[yellow]No output from p4 findreviewers[/yellow]")

        # Wait for user to press enter before returning
        console.print("\n[dim]Press enter to continue...[/dim]", end="")
        input()
        return True

    except subprocess.CalledProcessError as e:
        error_msg = f"p4 findreviewers failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        elif e.stdout:
            error_msg += f": {e.stdout.strip()}"
        console.print(f"[red]{error_msg}[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]p4 command not found[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Unexpected error running findreviewers: {str(e)}[/red]")
        return False


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
    # Find all tags (lines starting with uppercase words followed by colon or equals)
    # Tags are things like "Bug:", "Test:", "BUG=", "R=", etc.
    lines = description.split("\n")
    tag_pattern = re.compile(r"^[A-Z][A-Za-z_\s-]*[=:]")

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
        # Scenario 2: Don't modify R= tag, just add startblock section
        # R= should remain as "R=startblock" and the reviewer will be added by startblock

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
        result_lines = content_lines + ["", startblock_section]
        if tag_lines:
            result_lines.extend([""] + tag_lines)
        return "\n".join(result_lines)

    elif num_reviewers == 2 and not has_valid_parent:
        # Scenario 3: Replace R=startblock with R=<reviewer1>,startblock and add section
        # Need to replace in the entire description to find R= tag
        tag_lines_str = "\n".join(tag_lines)
        tag_lines_str = tag_lines_str.replace(
            "R=startblock", f"R={reviewers[0]},startblock"
        )
        modified_tag_lines = tag_lines_str.split("\n")

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
        result_lines = content_lines + ["", startblock_section]
        if modified_tag_lines:
            result_lines.extend([""] + modified_tag_lines)
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
            result_lines.extend([""] + tag_lines)
        return "\n".join(result_lines)


def prepare_mail(changespec: ChangeSpec, console: Console) -> MailPrepResult | None:
    """Prepare for mailing a CL with startblock configuration.

    This performs all the prep work (reviewer prompts, description modification,
    clipboard copy, nvim editing) but does NOT run hg mail or update the project file.

    Args:
        changespec: The ChangeSpec to prepare for mailing
        console: Rich console for output

    Returns:
        MailPrepResult if successful (with should_mail indicating user's choice),
        None if the operation was aborted or failed.
    """
    # Get target directory
    try:
        target_dir = get_workspace_directory(changespec.project_basename)
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        return None

    # Prompt for reviewers (optional) - loop to handle @ input for findreviewers
    while True:
        console.print(
            "\n[cyan]Enter reviewers (1 or 2, space-separated, @ for findreviewers, "
            "or Enter to skip):[/cyan] ",
            end="",
        )
        try:
            reviewers_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Aborted[/yellow]")
            return None

        # Check for @ input - run findreviewers and reprompt
        if reviewers_input == "@":
            _run_findreviewers(target_dir, console)
            continue  # Loop back to prompt for reviewers again

        reviewers = reviewers_input.split()
        if reviewers and len(reviewers) not in [1, 2]:
            console.print(
                "[red]Error: Must provide exactly 1 or 2 reviewers (space-separated)[/red]"
            )
            return None

        break  # Valid input, exit loop

    # Only modify description and reword if reviewers were provided
    if reviewers:
        # Get current CL description
        console.print("[cyan]Getting CL description...[/cyan]")
        success, description = _get_cl_description(target_dir, console)
        if not success or not description:
            return None

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
                    console.print(
                        "[red]Error: Could not get parent branch number[/red]"
                    )
                    # Try to restore current branch
                    subprocess.run(
                        ["bb_hg_update", current_branch],
                        cwd=target_dir,
                        capture_output=True,
                        text=True,
                    )
                    return None

            except subprocess.CalledProcessError as e:
                console.print(
                    f"[red]Error updating to parent branch "
                    f"(exit code {e.returncode}, cwd: {target_dir})[/red]"
                )
                return None
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
                        f"[yellow]Warning: Could not restore to branch "
                        f"{current_branch} (cwd: {target_dir})[/yellow]"
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
            console.print(
                "[green]✓ Modified CL description copied to clipboard![/green]"
            )
        except subprocess.CalledProcessError as e:
            console.print(
                f"[red]FATAL: {clipboard_cmd[0]} failed "
                f"(exit code {e.returncode})[/red]"
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
    else:
        console.print("[cyan]No reviewers provided - skipping reword step[/cyan]")

    # Prompt user before mailing
    console.print("\n[cyan]Do you want to mail the CL now? (y/n):[/cyan] ", end="")
    try:
        mail_response = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Aborted[/yellow]")
        return None

    should_mail = mail_response in ["y", "yes"]
    if not should_mail:
        console.print("[yellow]User declined to mail[/yellow]")

    return MailPrepResult(should_mail=should_mail, target_dir=target_dir)


def execute_mail(changespec: ChangeSpec, target_dir: str, console: Console) -> bool:
    """Execute the hg mail command to mail the CL.

    This does NOT update the project file - the caller is responsible for
    updating the status appropriately.

    Args:
        changespec: The ChangeSpec to mail
        target_dir: The workspace directory for the CL
        console: Rich console for output

    Returns:
        True if mailing succeeded, False otherwise
    """
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
    return True


def handle_mail(changespec: ChangeSpec, console: Console) -> bool:
    """Handle mailing a CL with startblock configuration.

    This is the main entry point for the "m" (mail) action. It performs
    mail prep, executes the mail command, and updates the project file.

    Args:
        changespec: The ChangeSpec to mail
        console: Rich console for output

    Returns:
        True if mailing succeeded, False otherwise
    """
    # Run mail prep
    prep_result = prepare_mail(changespec, console)
    if prep_result is None:
        return False

    if not prep_result.should_mail:
        return False

    # Execute the mail command
    success = execute_mail(changespec, prep_result.target_dir, console)
    if not success:
        return False

    # Remove READY TO MAIL suffix if present before transitioning
    remove_ready_to_mail_suffix(changespec.file_path, changespec.name)

    # Update status to "Mailed"
    console.print("[cyan]Updating status to 'Mailed'...[/cyan]")
    status_success, old_status, status_error, _ = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        "Mailed",
        validate=True,
    )
    if status_success:
        console.print(
            f"[green]Status updated: {old_status if old_status else 'Drafted'} → Mailed[/green]"
        )
        return True
    else:
        console.print(
            f"[yellow]Warning: CL was mailed but status update failed: "
            f"{status_error if status_error else 'Unknown error'}[/yellow]"
        )
        return True  # Still return True since mailing succeeded

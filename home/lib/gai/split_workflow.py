"""Workflow for splitting a CL into multiple smaller CLs."""

import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich.console import Console
from rich_utils import print_status, print_workflow_header
from shared_utils import (
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_shell_command,
)
from split_spec import (
    SplitSpec,
    format_split_spec_as_markdown,
    parse_split_spec,
    topological_sort_entries,
    validate_split_spec,
)
from work.changespec import find_all_changespecs
from work.revert import revert_changespec
from workflow_base import BaseWorkflow


def _generate_timestamp() -> str:
    """Generate timestamp in YYmmddHHMMSS format."""
    eastern = ZoneInfo("America/New_York")
    return datetime.now(eastern).strftime("%y%m%d%H%M%S")


def _get_splits_directory() -> str:
    """Get the path to the splits directory (~/.gai/splits/)."""
    return os.path.expanduser("~/.gai/splits")


def _archive_spec_file(name: str, spec_content: str, timestamp: str) -> str:
    """Save spec file to ~/.gai/splits/<NAME>_<timestamp>.yml.

    Args:
        name: The CL name.
        spec_content: The YAML content of the spec.
        timestamp: The timestamp for the filename.

    Returns:
        The archive path with ~ for display.
    """
    splits_dir = _get_splits_directory()
    Path(splits_dir).mkdir(parents=True, exist_ok=True)

    archive_path = os.path.join(splits_dir, f"{name}_{timestamp}.yml")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(spec_content)

    # Return path with ~ for display
    return archive_path.replace(str(Path.home()), "~")


def _get_editor() -> str:
    """Get the editor to use for editing files.

    Returns:
        The editor command to use.
    """
    editor = os.environ.get("EDITOR")
    if editor:
        return editor

    # Fall back to nvim if it exists
    try:
        result = subprocess.run(
            ["which", "nvim"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return "nvim"
    except Exception:
        pass

    return "vim"


def _create_and_edit_spec(name: str, timestamp: str) -> tuple[str, str] | None:
    """Create empty spec file, open in editor, and archive.

    Args:
        name: The CL name for the spec.
        timestamp: The timestamp for archiving.

    Returns:
        Tuple of (spec_content, archive_path) or None if user cancelled.
    """
    # Create temp file for editing
    fd, temp_path = tempfile.mkstemp(suffix=".yml", prefix=f"{name}_split_")
    os.close(fd)

    # Get workspace name prefix
    ws_result = run_shell_command("workspace_name", capture_output=True)
    ws_prefix = f"{ws_result.stdout.strip()}_" if ws_result.returncode == 0 else ""

    # Write empty template
    template = f"""- name: {ws_prefix}
  description:
- name: {ws_prefix}
  description:
  parent: {ws_prefix}
"""

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(template)

    # Open in editor
    editor = _get_editor()
    subprocess.run([editor, temp_path], check=False)

    # Check if user saved content
    with open(temp_path, encoding="utf-8") as f:
        content = f.read()

    # Clean up temp file
    os.unlink(temp_path)

    # Check if content is essentially empty
    content_stripped = content.strip()
    if not content_stripped or content_stripped == template.strip():
        return None

    # Try to parse to validate
    try:
        parse_split_spec(content)
    except ValueError as e:
        print_status(f"Invalid SplitSpec: {e}", "error")
        return None

    # Archive the spec file
    archive_path = _archive_spec_file(name, content, timestamp)

    return (content, archive_path)


def _load_and_archive_spec(
    name: str, spec_path: str, timestamp: str
) -> tuple[str, str]:
    """Load existing spec file and archive it.

    Args:
        name: The CL name.
        spec_path: Path to the existing spec file.
        timestamp: The timestamp for archiving.

    Returns:
        Tuple of (spec_content, archive_path).
    """
    with open(spec_path, encoding="utf-8") as f:
        content = f.read()

    archive_path = _archive_spec_file(name, content, timestamp)
    return (content, archive_path)


def _has_children(name: str) -> bool:
    """Check if any non-reverted ChangeSpec has this one as a parent.

    Args:
        name: The ChangeSpec name to check.

    Returns:
        True if any non-reverted ChangeSpec has this one as parent.
    """
    all_cs = find_all_changespecs()
    for cs in all_cs:
        if cs.parent == name and cs.status != "Reverted":
            return True
    return False


def _get_name_from_branch() -> str | None:
    """Get the CL name from the current branch.

    Returns:
        The branch name or None if not available.
    """
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return name if name else None


def _prompt_for_revert(name: str, console: Console) -> bool:
    """Prompt user to revert the original CL and execute if confirmed.

    Args:
        name: The name of the ChangeSpec to revert.
        console: Rich console for output.

    Returns:
        True if revert was successful, False otherwise.
    """
    console.print(f"\n[yellow]Revert the original CL '{name}'?[/yellow]")
    response = input("(y/n): ").strip().lower()

    if response == "y":
        all_cs = find_all_changespecs()
        target = None
        for cs in all_cs:
            if cs.name == name:
                target = cs
                break

        if target:
            success, error = revert_changespec(target, console)
            if success:
                console.print("[green]Original CL reverted successfully[/green]")
                return True
            else:
                console.print(f"[red]Failed to revert: {error}[/red]")
                return False
        else:
            console.print(f"[red]ChangeSpec '{name}' not found[/red]")
            return False

    return False


def _build_split_prompt(
    diff_path: str,
    spec: SplitSpec,
    default_parent: str,
    bug: str,
    original_name: str,
    spec_archive_path: str,
) -> str:
    """Build the prompt for the Gemini agent to perform the split.

    Args:
        diff_path: Path to the saved diff file.
        spec: The parsed SplitSpec.
        default_parent: The default parent for entries without explicit parents.
        bug: The bug number.
        original_name: The name of the CL being split.
        spec_archive_path: Path to the archived spec file.

    Returns:
        The formatted prompt string.
    """
    # Build the note for gai commit -n option
    note = f"Split from {original_name} ({spec_archive_path})"

    # Sort entries for processing order
    sorted_entries = topological_sort_entries(spec.entries)

    # Format the spec as markdown
    spec_markdown = format_split_spec_as_markdown(spec)

    # Build optional bug section and commit flag
    bug_section = f"\n## Bug Number\n{bug}\n" if bug else ""
    bug_flag = f"-b {bug} " if bug else ""

    prompt = f"""# CL Split Task

You need to split the changes in the diff file into multiple new CLs as specified below.

## Original Diff
@{diff_path}

## Split Specification

{spec_markdown}
{bug_section}
## Instructions

For each entry in the split specification (process in the order shown - parents before children):

1. **Navigate to the parent CL:**
   - If `parent` is specified in the entry: run `bb_hg_update <parent>`
   - Otherwise: run `bb_hg_update {default_parent}`

2. **Make the file changes for this CL based on its description.**
   - Analyze the original diff and determine which changes belong to this CL
   - Use the description to understand what this CL should contain
   - Apply EXACTLY the portions of the diff that logically belong to this CL

3. **Create the description file** at `bb/gai/<name>_desc.txt` with the description from the spec.

4. **Run:** `gai commit {bug_flag}-n "{note}" <name> bb/gai/<name>_desc.txt`

5. **Repeat** for the next entry.

## Processing Order

Process the entries in this order (parents before children):
{chr(10).join(f"{i + 1}. {e.name}" + (f" (parent: {e.parent})" if e.parent else "") for i, e in enumerate(sorted_entries))}

## IMPORTANT

- Process entries in the order specified above (depth-first, parents before children)
- Each file change must exactly match portions of the original diff
- Use each CL's description to determine which changes belong to it
- After making changes, verify they compile/work before committing
"""
    return prompt


class SplitWorkflow(BaseWorkflow):
    """A workflow for splitting a CL into multiple smaller CLs."""

    def __init__(
        self,
        name: str | None,
        spec_path: str | None,
        create_spec: bool,
    ) -> None:
        """Initialize the split workflow.

        Args:
            name: Name of the ChangeSpec to split (or None to use current branch).
            spec_path: Path to an existing SplitSpec file (or None).
            create_spec: If True, create a new spec file and open in editor.
        """
        self._cl_name = name
        self._spec_path = spec_path
        self._create_spec = create_spec

    @property
    def name(self) -> str:
        return "split"

    @property
    def description(self) -> str:
        return "Split a CL into multiple smaller CLs"

    def run(self) -> bool:
        """Execute the split workflow.

        Returns:
            True if successful, False otherwise.
        """
        console = Console()
        workflow_tag = generate_workflow_tag()

        # Print workflow header
        print_workflow_header("split", workflow_tag)

        # Step 1: Determine NAME (from arg or branch_name)
        cl_name = self._cl_name
        if cl_name is None:
            cl_name = _get_name_from_branch()
            if cl_name is None:
                print_status(
                    "Could not determine CL name from branch. Please provide NAME.",
                    "error",
                )
                return False
            print_status(f"Using current branch: {cl_name}", "info")

        # Step 2: Validate target CL has no children
        print_status("Checking for child CLs...", "progress")
        if _has_children(cl_name):
            print_status(
                f"Cannot split: CL '{cl_name}' has child CLs. "
                "Split child CLs first or restructure the hierarchy.",
                "error",
            )
            return False
        print_status("No child CLs found.", "success")

        # Generate timestamp for archiving
        timestamp = _generate_timestamp()

        # Step 3: Handle spec file (create/edit or load existing)
        print_status("Handling split specification...", "progress")
        if self._create_spec:
            # Create new spec and edit
            result = _create_and_edit_spec(cl_name, timestamp)
            if result is None:
                print_status(
                    "No valid split specification provided. Aborting.", "error"
                )
                return False
            spec_content, archive_path = result
        elif self._spec_path:
            # Load existing spec
            if not os.path.isfile(self._spec_path):
                print_status(f"Spec file not found: {self._spec_path}", "error")
                return False
            spec_content, archive_path = _load_and_archive_spec(
                cl_name, self._spec_path, timestamp
            )
        else:
            print_status("No spec file provided. Use -s option.", "error")
            return False

        # Parse and validate the spec
        try:
            spec = parse_split_spec(spec_content)
        except ValueError as e:
            print_status(f"Invalid split spec: {e}", "error")
            return False

        is_valid, error_msg = validate_split_spec(spec)
        if not is_valid:
            print_status(f"Invalid split spec: {error_msg}", "error")
            return False

        print_status(f"Spec archived to: {archive_path}", "success")
        print_status(
            f"Split will create {len(spec.entries)} new CL(s).",
            "info",
        )

        # Step 4: Navigate to target CL
        print_status(f"Navigating to CL: {cl_name}...", "progress")
        nav_result = run_shell_command(f"bb_hg_update {cl_name}", capture_output=True)
        if nav_result.returncode != 0:
            print_status(f"Failed to navigate to CL: {nav_result.stderr}", "error")
            return False
        print_status(f"Now on CL: {cl_name}", "success")

        # Step 5: Save diff, get bug, determine default_parent from ChangeSpec
        print_status("Saving diff and gathering metadata...", "progress")

        # Create bb/gai directory if needed
        bb_gai_dir = "bb/gai"
        Path(bb_gai_dir).mkdir(parents=True, exist_ok=True)

        # Save diff
        diff_path = f"{bb_gai_dir}/{cl_name}.diff"
        diff_result = run_shell_command("branch_diff", capture_output=True)
        if diff_result.returncode != 0:
            print_status(f"Failed to get branch diff: {diff_result.stderr}", "error")
            return False
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(diff_result.stdout)
        print_status(f"Diff saved to: {diff_path}", "success")

        # Get bug number
        bug_result = run_shell_command("branch_bug", capture_output=True)
        if bug_result.returncode != 0:
            print_status(f"Failed to get bug number: {bug_result.stderr}", "error")
            return False
        bug = bug_result.stdout.strip()
        print_status(f"Bug number: {bug}", "info")

        # Get default_parent from ChangeSpec's PARENT field (or "p4head" if none)
        all_cs = find_all_changespecs()
        target_cs = next((cs for cs in all_cs if cs.name == cl_name), None)
        if target_cs and target_cs.parent:
            default_parent = target_cs.parent
        else:
            default_parent = "p4head"
        print_status(f"Default parent: {default_parent}", "info")

        # Navigate to parent
        print_status(f"Navigating to parent: {default_parent}...", "progress")
        parent_nav_result = run_shell_command(
            f"bb_hg_update {default_parent}", capture_output=True
        )
        if parent_nav_result.returncode != 0:
            print_status(
                f"Warning: Failed to navigate to parent: {parent_nav_result.stderr}",
                "warning",
            )
        else:
            print_status(f"Now on parent: {default_parent}", "success")

        # Create artifacts directory
        artifacts_dir = create_artifacts_directory("split")
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")

        # Initialize the gai.md log
        initialize_gai_log(artifacts_dir, "split", workflow_tag)

        # Step 6: Build and invoke Gemini agent
        print_status("Building split prompt...", "progress")
        prompt = _build_split_prompt(
            diff_path=diff_path,
            spec=spec,
            default_parent=default_parent,
            bug=bug,
            original_name=cl_name,
            spec_archive_path=archive_path,
        )

        # Save prompt to artifacts
        prompt_path = os.path.join(artifacts_dir, "split_prompt.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print_status(f"Prompt saved to: {prompt_path}", "info")

        print_status("Invoking Gemini agent to perform split...", "progress")
        model = GeminiCommandWrapper(model_size="big")
        model.set_logging_context(
            agent_type="split",
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
            workflow="split",
        )

        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = model.invoke(messages)

        # Save the response
        response_path = os.path.join(artifacts_dir, "split_response.txt")
        with open(response_path, "w", encoding="utf-8") as f:
            f.write(ensure_str_content(response.content))
        print_status(f"Response saved to: {response_path}", "success")

        print_status("Split agent completed!", "success")

        # Finalize the gai.md log
        finalize_gai_log(artifacts_dir, "split", workflow_tag, True)

        # Step 7: Prompt user to revert original CL
        _prompt_for_revert(cl_name, console)

        return True

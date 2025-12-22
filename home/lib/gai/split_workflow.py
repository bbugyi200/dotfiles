"""Workflow for splitting a CL into multiple smaller CLs."""

import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from chat_history import list_chat_histories, load_chat_history, save_chat_history
from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich.console import Console
from rich.syntax import Syntax
from rich_utils import print_status, print_workflow_header
from running_field import claim_workspace
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


def _get_project_file_and_workspace_num(
    project_name: str,
) -> tuple[str | None, int | None]:
    """Get the project file path and workspace number.

    Args:
        project_name: The project/workspace name.

    Returns:
        Tuple of (project_file, workspace_num), or (None, None) if not found.
    """
    # Construct project file path
    project_file = os.path.expanduser(
        f"~/.gai/projects/{project_name}/{project_name}.gp"
    )
    if not os.path.exists(project_file):
        return (None, None)

    # Determine workspace number from current directory
    cwd = os.getcwd()

    # Check if we're in a numbered workspace share
    workspace_num = 1
    for n in range(2, 101):
        workspace_suffix = f"{project_name}_{n}"
        if workspace_suffix in cwd:
            workspace_num = n
            break

    return (project_file, workspace_num)


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


def _build_spec_generator_prompt(
    cl_name: str,
    workspace_name: str,
    diff_path: str,
) -> str:
    """Build the prompt for the agent to generate a split spec.

    Args:
        cl_name: The name of the CL being split.
        workspace_name: The workspace name prefix for CL names.
        diff_path: Path to the diff file.

    Returns:
        The formatted prompt string.
    """
    return f"""# Generate Split Specification

You need to analyze the changes in a CL and generate a YAML split specification
that divides the work into multiple smaller, focused CLs.

## Original Diff
@{diff_path}

## Guidelines

Refer to the following files for guidance:
* @~/bb/docs/small_cls.md - Guidelines for determining how many CLs to create
* @~/bb/docs/cl_descriptions.md - Guidelines for writing good CL descriptions

## CRITICAL REQUIREMENTS

1. **All 'name' field values MUST be prefixed with `{workspace_name}_`**
   - Example: `{workspace_name}_add_logging`, `{workspace_name}_refactor_utils`

2. Output ONLY valid YAML - no explanation, no markdown code fences, just raw YAML

3. Each entry should have:
   - `name`: The CL name (with {workspace_name}_ prefix)
   - `description`: A clear, concise description following the CL description guidelines
   - `parent`: (optional) The name of the parent CL if this builds on another split CL

4. **PRIORITIZE PARALLEL CLs**: Only use `parent` when there is a TRUE dependency
   - CL B should only be a child of CL A if B's changes cannot be applied without A's changes
   - If two CLs modify different files or independent parts of the codebase, they should be PARALLEL (no parent)
   - Parallel CLs can be reviewed and submitted independently, which is faster
   - When in doubt, prefer parallel CLs over creating unnecessary parent-child chains

## Expected Output Format

IMPORTANT: Use TWO blank lines between each entry for readability.

```yaml
# Parallel CLs (no parent - can be reviewed/submitted independently)
- name: {workspace_name}_first_change
  description: |
    Brief summary of first change.


- name: {workspace_name}_second_change
  description: |
    Brief summary of second change (independent of first).


# Child CL (only when truly dependent on parent)
- name: {workspace_name}_dependent_change
  description: |
    This change requires first_change to be applied first.
  parent: {workspace_name}_first_change
```

Generate the split specification now. Output ONLY the YAML content."""


def _extract_yaml_from_response(response: str) -> str:
    """Extract YAML content from agent response.

    The agent may wrap the YAML in markdown code fences. This function
    extracts the raw YAML content.

    Args:
        response: The agent response text.

    Returns:
        The extracted YAML content.
    """
    # Try to extract from markdown code fences
    yaml_pattern = r"```(?:ya?ml)?\s*\n(.*?)```"
    match = re.search(yaml_pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # If no code fence, assume the whole response is YAML
    # But strip any leading/trailing whitespace
    return response.strip()


def _prompt_for_spec_action(
    console: Console,
) -> Literal["accept", "edit", "reject"] | str:
    """Prompt user for action on generated spec.

    Args:
        console: Rich console for output.

    Returns:
        "accept", "edit", "reject", or a custom prompt string for rerun.
    """
    console.print(
        "\n[bold cyan]Split spec generated. What would you like to do?[/bold cyan]"
    )
    console.print("  [green]a[/green] - Accept and use this spec")
    console.print("  [yellow]e[/yellow] - Edit the spec in your editor")
    console.print("  [red]x[/red] - Reject and abort")
    console.print("  [blue]<text>[/blue] - Provide feedback to regenerate")
    console.print()

    response = input("Choice: ").strip()

    if response.lower() == "a":
        return "accept"
    elif response.lower() == "e":
        return "edit"
    elif response.lower() == "x":
        return "reject"
    else:
        return response


def _edit_spec_content(content: str, name: str) -> str | None:
    """Open spec content in editor for user modification.

    Args:
        content: The YAML content to edit.
        name: The CL name for temp file naming.

    Returns:
        The edited content, or None if cancelled.
    """
    # Create temp file for editing
    fd, temp_path = tempfile.mkstemp(suffix=".yml", prefix=f"{name}_split_")
    os.close(fd)

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Open in editor
    editor = _get_editor()
    subprocess.run([editor, temp_path], check=False)

    # Read edited content
    with open(temp_path, encoding="utf-8") as f:
        edited_content = f.read()

    # Clean up temp file
    os.unlink(temp_path)

    # Check if content is essentially empty
    if not edited_content.strip():
        return None

    return edited_content


def _generate_spec_with_agent(
    cl_name: str,
    workspace_name: str,
    diff_path: str,
    timestamp: str,
    console: Console,
    artifacts_dir: str,
    workflow_tag: str,
) -> tuple[str, str] | None:
    """Generate a split spec using an agent with user interaction loop.

    Args:
        cl_name: The name of the CL being split.
        workspace_name: The workspace name prefix for CL names.
        diff_path: Path to the diff file.
        timestamp: The timestamp for archiving.
        console: Rich console for output.
        artifacts_dir: Directory for artifacts.
        workflow_tag: The workflow tag.

    Returns:
        Tuple of (spec_content, archive_path) or None if user rejected.
    """
    print_status("Generating split spec with agent...", "progress")

    # Build initial prompt
    prompt = _build_spec_generator_prompt(cl_name, workspace_name, diff_path)

    # Initialize agent
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="split-spec-generator",
        iteration=1,
        workflow_tag=workflow_tag,
        artifacts_dir=artifacts_dir,
        workflow="split",
    )

    # Track conversation for reruns
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    iteration = 1

    while True:
        # Invoke agent
        response = model.invoke(messages)
        response_text = ensure_str_content(response.content)

        # Save chat history
        prompt_text = ensure_str_content(messages[-1].content)
        save_chat_history(
            prompt=prompt_text,
            response=response_text,
            workflow="split-spec",
            agent="generator",
        )

        # Extract YAML from response
        yaml_content = _extract_yaml_from_response(response_text)

        # Try to parse and validate
        try:
            spec = parse_split_spec(yaml_content)
            is_valid, error = validate_split_spec(spec)
            if not is_valid:
                raise ValueError(error)
            print_status(
                f"Valid spec generated with {len(spec.entries)} entries.",
                "success",
            )
        except ValueError as e:
            console.print(f"[red]Invalid spec: {e}[/red]")
            console.print("[yellow]The agent will be asked to fix this.[/yellow]")

            # Add error feedback and retry
            error_prompt = f"""The generated YAML was invalid: {e}

Please fix the issue and regenerate the split specification.
Remember:
- All 'name' values must be prefixed with `{workspace_name}_`
- Output ONLY valid YAML, no markdown fences or explanations"""

            messages.append(response)
            messages.append(HumanMessage(content=error_prompt))
            iteration += 1
            model.set_logging_context(
                agent_type="split-spec-generator",
                iteration=iteration,
                workflow_tag=workflow_tag,
                artifacts_dir=artifacts_dir,
                workflow="split",
            )
            continue

        # Show the spec YAML to user
        console.print("\n[bold]Generated Split Specification:[/bold]")
        console.print("[dim]" + "─" * 60 + "[/dim]")
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
        console.print("[dim]" + "─" * 60 + "[/dim]")

        # Prompt for action
        action = _prompt_for_spec_action(console)

        if action == "accept":
            # Archive and return
            archive_path = _archive_spec_file(cl_name, yaml_content, timestamp)
            return (yaml_content, archive_path)

        elif action == "edit":
            # Open in editor
            edited_content = _edit_spec_content(yaml_content, cl_name)
            if edited_content is None:
                print_status("Edit cancelled (empty content).", "warning")
                continue

            # Validate edited content
            try:
                edited_spec = parse_split_spec(edited_content)
                is_valid, error = validate_split_spec(edited_spec)
                if not is_valid:
                    raise ValueError(error)
            except ValueError as e:
                print_status(f"Edited spec is invalid: {e}", "error")
                continue

            # Archive and return
            archive_path = _archive_spec_file(cl_name, edited_content, timestamp)
            return (edited_content, archive_path)

        elif action == "reject":
            print_status("Spec generation rejected by user.", "warning")
            return None

        else:
            # Treat as rerun prompt - user provided feedback
            console.print(f"[cyan]Regenerating with feedback: {action}[/cyan]")

            # Load the previous chat history (same pattern as gai rerun)
            histories = list_chat_histories()
            split_spec_histories = [h for h in histories if h.startswith("split-spec_")]

            if split_spec_histories:
                # Load the most recent split-spec history
                previous_history = load_chat_history(
                    split_spec_histories[0], increment_headings=True
                )
                rerun_prompt = f"""# Previous Conversation

{previous_history}

---

# User Feedback

{action}

---

# Requirements

1. All 'name' field values MUST be prefixed with `{workspace_name}_`
2. Output ONLY valid YAML - no explanation, no markdown code fences, just raw YAML
3. PRIORITIZE PARALLEL CLs - only use `parent` when there is a TRUE dependency

Please regenerate the split specification incorporating the user's feedback."""
            else:
                # Fallback if no history found (shouldn't happen)
                rerun_prompt = f"""# Regenerate Split Specification

You previously generated a split specification for a CL, but the user has requested changes.

## Original Diff
@{diff_path}

## Previous Generated Spec
```yaml
{yaml_content}
```

## User Feedback
{action}

## Requirements
1. All 'name' field values MUST be prefixed with `{workspace_name}_`
2. Output ONLY valid YAML - no explanation, no markdown code fences, just raw YAML
3. PRIORITIZE PARALLEL CLs - only use `parent` when there is a TRUE dependency

Please regenerate the split specification incorporating the user's feedback."""

            messages.append(response)
            messages.append(HumanMessage(content=rerun_prompt))
            iteration += 1
            model.set_logging_context(
                agent_type="split-spec-generator",
                iteration=iteration,
                workflow_tag=workflow_tag,
                artifacts_dir=artifacts_dir,
                workflow="split",
            )


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

    # Build commit flag for bug number
    bug_flag = f"-b {bug} " if bug else ""

    prompt = f"""Can you help me replicate the changes shown in the @{diff_path} file EXACTLY by
splitting the changes across multiple new CLs (specified below)?

## Split Specification
{spec_markdown}

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
After making changes, verify they compile/work before committing
"""
    return prompt


class SplitWorkflow(BaseWorkflow):
    """A workflow for splitting a CL into multiple smaller CLs."""

    def __init__(
        self,
        name: str | None,
        spec_path: str | None,
        create_spec: bool,
        generate_spec: bool = False,
    ) -> None:
        """Initialize the split workflow.

        Args:
            name: Name of the ChangeSpec to split (or None to use current branch).
            spec_path: Path to an existing SplitSpec file (or None).
            create_spec: If True, create a new spec file and open in editor.
            generate_spec: If True, use an agent to generate the spec.
        """
        self._cl_name = name
        self._spec_path = spec_path
        self._create_spec = create_spec
        self._generate_spec = generate_spec

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

        # Step 3: Navigate to target CL (needed for diff before spec generation)
        print_status(f"Navigating to CL: {cl_name}...", "progress")
        nav_result = run_shell_command(f"bb_hg_update {cl_name}", capture_output=True)
        if nav_result.returncode != 0:
            print_status(f"Failed to navigate to CL: {nav_result.stderr}", "error")
            return False
        print_status(f"Now on CL: {cl_name}", "success")

        # Step 4: Save diff and gather metadata
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

        # Get workspace name for agent-based generation
        ws_result = run_shell_command("workspace_name", capture_output=True)
        if ws_result.returncode != 0:
            print_status(f"Failed to get workspace name: {ws_result.stderr}", "error")
            return False
        workspace_name = ws_result.stdout.strip()

        # Claim workspace in project file's RUNNING field
        project_file, workspace_num = _get_project_file_and_workspace_num(
            workspace_name
        )
        if project_file and workspace_num:
            claim_workspace(project_file, workspace_num, "split", cl_name)

        # Get default_parent from ChangeSpec's PARENT field (or "p4head" if none)
        all_cs = find_all_changespecs()
        target_cs = next((cs for cs in all_cs if cs.name == cl_name), None)
        if target_cs and target_cs.parent:
            default_parent = target_cs.parent
        else:
            default_parent = "p4head"
        print_status(f"Default parent: {default_parent}", "info")

        # Create artifacts directory early (needed for agent-based generation)
        artifacts_dir = create_artifacts_directory("split")
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")

        # Initialize the gai.md log
        initialize_gai_log(artifacts_dir, "split", workflow_tag)

        # Step 5: Handle spec file (create/edit, load existing, or generate)
        print_status("Handling split specification...", "progress")
        if self._generate_spec:
            # Use agent to generate spec
            result = _generate_spec_with_agent(
                cl_name=cl_name,
                workspace_name=workspace_name,
                diff_path=diff_path,
                timestamp=timestamp,
                console=console,
                artifacts_dir=artifacts_dir,
                workflow_tag=workflow_tag,
            )
            if result is None:
                print_status("Spec generation aborted by user.", "error")
                return False
            spec_content, archive_path = result
        elif self._create_spec:
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

"""Agent and prompt building functions for the split workflow."""

import re
from typing import Literal

from chat_history import list_chat_histories, load_chat_history, save_chat_history
from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich.console import Console
from rich.syntax import Syntax
from rich_utils import print_status
from shared_utils import ensure_str_content
from split_spec import (
    SplitSpec,
    format_split_spec_as_markdown,
    parse_split_spec,
    topological_sort_entries,
    validate_split_spec,
)

from .spec import archive_spec_file, edit_spec_content


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


def generate_spec_with_agent(
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
            archive_path = archive_spec_file(cl_name, yaml_content, timestamp)
            return (yaml_content, archive_path)

        elif action == "edit":
            # Open in editor
            edited_content = edit_spec_content(yaml_content, cl_name)
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
            archive_path = archive_spec_file(cl_name, edited_content, timestamp)
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


def build_split_prompt(
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
"""
    return prompt

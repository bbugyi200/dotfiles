"""Agent and prompt building functions for the split workflow."""

from typing import Literal

import yaml  # type: ignore[import-untyped]
from chat_history import list_chat_histories, load_chat_history, save_chat_history
from gai_utils import generate_timestamp
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
from xprompt import (
    OutputValidationError,
    extract_structured_content,
    generate_format_instructions,
    get_primary_output_schema,
    process_xprompt_references,
)

from .spec import archive_spec_file, edit_spec_content


def _escape_for_xprompt(text: str) -> str:
    """Escape text for use in an xprompt argument string.

    Escapes double quotes and backslashes.

    Args:
        text: The text to escape.

    Returns:
        The escaped text safe for use in xprompt argument.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _build_spec_generator_prompt(
    cl_name: str,
    workspace_name: str,
    diff_path: str,
) -> str:
    """Build the prompt for the agent to generate a split spec using xprompt.

    Args:
        cl_name: The name of the CL being split (unused, kept for API compatibility).
        workspace_name: The workspace name prefix for CL names.
        diff_path: Path to the diff file.

    Returns:
        The formatted prompt string.
    """
    del cl_name  # Unused, kept for API compatibility
    escaped_workspace = _escape_for_xprompt(workspace_name)
    escaped_diff = _escape_for_xprompt(diff_path)
    prompt_text = f'#split_spec_generator(workspace_name="{escaped_workspace}", diff_path="{escaped_diff}")'

    # Get output schema BEFORE expansion (same pattern as wrapper.py:331-332)
    output_spec = get_primary_output_schema(prompt_text)

    # Expand the xprompt
    expanded = process_xprompt_references(prompt_text)

    # Append format instructions if we have an output schema (same pattern as wrapper.py:352-355)
    if output_spec is not None:
        format_instructions = generate_format_instructions(output_spec)
        if format_instructions:
            expanded = expanded + format_instructions

    return expanded


def _prompt_for_spec_action(
    console: Console,
    yolo: bool = False,
) -> Literal["accept", "edit", "reject"] | str:
    """Prompt user for action on generated spec.

    Args:
        console: Rich console for output.
        yolo: If True, auto-approve without prompting.

    Returns:
        "accept", "edit", "reject", or a custom prompt string for rerun.
    """
    if yolo:
        console.print("\n[bold cyan]Auto-approving spec (--yolo mode)[/bold cyan]")
        return "accept"

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
    yolo: bool = False,
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
        yolo: If True, auto-approve the spec without user interaction.

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
        # Capture start timestamp for accurate duration calculation
        start_timestamp = generate_timestamp()

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
            timestamp=start_timestamp,
        )

        # Extract structured content from response
        try:
            data, _ = extract_structured_content(response_text)
            # Convert back to YAML for display
            yaml_content = yaml.dump(data, default_flow_style=False)
        except OutputValidationError:
            # Fallback to raw response if extraction fails
            yaml_content = response_text.strip()

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
            print_status("Split spec generation failed due to invalid output.", "error")
            return None

        # Show the spec YAML to user
        console.print("\n[bold]Generated Split Specification:[/bold]")
        console.print("[dim]" + "─" * 60 + "[/dim]")
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
        console.print("[dim]" + "─" * 60 + "[/dim]")

        # Prompt for action
        action = _prompt_for_spec_action(console, yolo=yolo)

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
2. PRIORITIZE PARALLEL CLs - only use `parent` when there is a TRUE dependency

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
2. PRIORITIZE PARALLEL CLs - only use `parent` when there is a TRUE dependency

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
    """Build the prompt for the Gemini agent to perform the split using xprompt.

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

    # Build processing order list
    processing_order = chr(10).join(
        f"{i + 1}. {e.name}" + (f" (parent: {e.parent})" if e.parent else "")
        for i, e in enumerate(sorted_entries)
    )

    # Build the xprompt call
    escaped_diff = _escape_for_xprompt(diff_path)
    escaped_spec = _escape_for_xprompt(spec_markdown)
    escaped_parent = _escape_for_xprompt(default_parent)
    escaped_bug = _escape_for_xprompt(bug_flag)
    escaped_note = _escape_for_xprompt(note)
    escaped_order = _escape_for_xprompt(processing_order)

    prompt_text = (
        f'#split_executor(diff_path="{escaped_diff}", '
        f'spec_markdown="{escaped_spec}", '
        f'default_parent="{escaped_parent}", '
        f'bug_flag="{escaped_bug}", '
        f'note="{escaped_note}", '
        f'processing_order="{escaped_order}")'
    )
    return process_xprompt_references(prompt_text)

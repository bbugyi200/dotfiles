"""Workflow for fixing failing hook commands using AI assistance."""

import os

from change_actions import execute_change_action, prompt_for_change_action
from chat_history import save_chat_history
from gai_utils import generate_timestamp
from gemini_wrapper import invoke_agent
from rich.console import Console
from shared_utils import ensure_str_content, generate_workflow_tag
from workflow_base import BaseWorkflow
from xprompt import process_xprompt_references


def _escape_for_xprompt(text: str) -> str:
    """Escape text for use in an xprompt argument string.

    Escapes double quotes and backslashes.

    Args:
        text: The text to escape.

    Returns:
        The escaped text safe for use in xprompt argument.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _build_fix_hook_prompt(hook_command: str, output_file: str) -> str:
    """Build the prompt for the fix-hook agent using the fix_hook xprompt.

    Args:
        hook_command: The failing hook command.
        output_file: Path to the file containing command output.

    Returns:
        The formatted prompt string.
    """
    escaped_command = _escape_for_xprompt(hook_command)
    escaped_output = _escape_for_xprompt(output_file)
    prompt_text = (
        f'#fix_hook(hook_command="{escaped_command}", output_file="{escaped_output}")'
    )
    return process_xprompt_references(prompt_text)


class FixHookWorkflow(BaseWorkflow):
    """A workflow for fixing failing hook commands."""

    def __init__(
        self,
        hook_output_file: str,
        hook_command: str,
    ) -> None:
        """Initialize the fix-hook workflow.

        Args:
            hook_output_file: Path to the file containing hook command output.
            hook_command: The failing hook command string.
        """
        self.hook_output_file = hook_output_file
        self.hook_command = hook_command
        self.console = Console()

    @property
    def name(self) -> str:
        return "fix-hook"

    @property
    def description(self) -> str:
        return "Fix a failing hook command using AI assistance"

    def run(self) -> bool:
        """Run the fix-hook workflow.

        Returns:
            True if successful (changes accepted/committed), False otherwise.
        """
        # Get current working directory
        target_dir = os.getcwd()

        # Generate shared timestamp for chat/diff files
        shared_timestamp = generate_timestamp()

        # Build the prompt
        prompt = _build_fix_hook_prompt(self.hook_command, self.hook_output_file)

        # Run the agent
        self.console.print("[cyan]Running fix-hook agent...[/cyan]")
        self.console.print(f"[dim]Command: {self.hook_command}[/dim]")
        self.console.print()

        try:
            response = invoke_agent(
                prompt,
                agent_type="fix-hook",
                model_size="big",
                suppress_output=False,
                workflow="fix-hook",
            )
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Workflow interrupted (Ctrl+C)[/yellow]")
            return False
        except Exception as e:
            self.console.print(f"[red]Agent failed: {e}[/red]")
            return False

        response_content = ensure_str_content(response.content)
        self.console.print(f"\n[green]Agent Response:[/green]\n{response_content}\n")

        # Save chat history
        chat_path = save_chat_history(
            prompt=prompt,
            response=response_content,
            workflow="fix-hook",
            timestamp=shared_timestamp,
        )

        # Build workflow name for the proposal note
        workflow_name = f"fix-hook {self.hook_command}"

        # Prompt for action on changes
        prompt_result = prompt_for_change_action(
            self.console,
            target_dir,
            workflow_name=workflow_name,
            chat_path=chat_path,
            shared_timestamp=shared_timestamp,
        )

        if prompt_result is None:
            self.console.print("\n[yellow]No changes detected.[/yellow]")
            print(f"\nChat history saved to: {chat_path}")
            return False

        action, action_args = prompt_result

        if action == "reject":
            self.console.print("[yellow]Changes rejected. Proposal saved.[/yellow]")
            print(f"\nChat history saved to: {chat_path}")
            return False

        # Execute the action (accept, commit, or purge)
        workflow_tag = generate_workflow_tag()
        success = execute_change_action(
            action=action,
            action_args=action_args,
            console=self.console,
            target_dir=target_dir,
            workflow_tag=workflow_tag,
            workflow_name="fix-hook",
            chat_path=chat_path,
            shared_timestamp=shared_timestamp,
        )

        print(f"\nChat history saved to: {chat_path}")
        return success

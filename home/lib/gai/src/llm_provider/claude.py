"""Claude Code LLM provider implementation."""

import os
import subprocess

from rich_utils import gemini_timer

from ._subprocess import stream_process_output
from .base import LLMProvider
from .types import ModelTier

# Map model tiers to Claude CLI aliases
_TIER_TO_MODEL: dict[ModelTier, str] = {
    "large": "opus",
    "small": "sonnet",
}


class ClaudeCodeProvider(LLMProvider):
    """LLM provider that invokes the Claude Code CLI tool."""

    def invoke(
        self,
        prompt: str,
        *,
        model_tier: ModelTier,
        suppress_output: bool = False,
    ) -> str:
        """Invoke Claude Code CLI with the given prompt.

        Args:
            prompt: The preprocessed prompt to send.
            model_tier: Which model tier to use ("large" or "small").
            suppress_output: If True, suppress real-time output to console.

        Returns:
            The response text from Claude.

        Raises:
            subprocess.CalledProcessError: If the Claude CLI process fails.
        """
        model_alias = _TIER_TO_MODEL[model_tier]

        # Build base command arguments
        base_args = [
            "claude",
            "-p",
            "--model",
            model_alias,
            "--output-format",
            "text",
            "--dangerously-skip-permissions",
        ]

        # Parse additional args from environment variable based on tier
        if model_tier == "large":
            extra_args_env = os.environ.get("GAI_CLAUDE_LARGE_ARGS")
        else:
            extra_args_env = os.environ.get("GAI_CLAUDE_SMALL_ARGS")

        if extra_args_env:
            for arg in extra_args_env.split():
                base_args.append(arg)

        # Start the process and stream output in real-time with timer
        timer_context = (
            gemini_timer("Waiting for Claude") if not suppress_output else None
        )

        if timer_context:
            with timer_context:
                response_content, stderr_content, return_code = self._run_subprocess(
                    base_args, prompt, suppress_output
                )
                # Add newline to separate agent output from timer
                print()
        else:
            response_content, stderr_content, return_code = self._run_subprocess(
                base_args, prompt, suppress_output
            )

        # Check if process failed
        if return_code != 0:
            error_content = f"Error running claude command (exit code {return_code})"
            if stderr_content:
                error_content += f": {stderr_content.strip()}"
            raise subprocess.CalledProcessError(
                return_code,
                base_args,
                output=response_content,
                stderr=stderr_content,
            )

        return response_content.strip()

    def _run_subprocess(
        self,
        args: list[str],
        prompt: str,
        suppress_output: bool,
    ) -> tuple[str, str, int]:
        """Run the Claude CLI subprocess.

        Args:
            args: Command-line arguments.
            prompt: Prompt to write to stdin.
            suppress_output: If True, suppress output.

        Returns:
            Tuple of (stdout_content, stderr_content, return_code).
        """
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Write prompt to stdin
        if process.stdin:
            process.stdin.write(prompt)
            process.stdin.close()

        # Stream output in real-time
        return stream_process_output(process, suppress_output=suppress_output)

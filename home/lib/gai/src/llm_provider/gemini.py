"""Gemini LLM provider implementation.

Extracts only the Gemini-specific subprocess logic from the old
GeminiCommandWrapper.invoke() method.
"""

import os
import subprocess

from rich_utils import gemini_timer

from ._subprocess import stream_process_output
from .base import LLMProvider
from .types import ModelTier


class GeminiProvider(LLMProvider):
    """LLM provider that invokes Google's Gemini CLI tool."""

    def invoke(
        self,
        prompt: str,
        *,
        model_tier: ModelTier,
        suppress_output: bool = False,
    ) -> str:
        """Invoke Gemini CLI with the given prompt.

        Args:
            prompt: The preprocessed prompt to send.
            model_tier: Which model tier to use ("large" or "small").
            suppress_output: If True, suppress real-time output to console.

        Returns:
            The response text from Gemini.

        Raises:
            subprocess.CalledProcessError: If the Gemini CLI process fails.
        """
        # Build base command arguments
        base_args = [
            "/google/bin/releases/gemini-cli/tools/gemini",
            "--yolo",
        ]

        # Parse additional args from environment variable based on tier
        # Check generic GAI_LLM_*_ARGS first, fall back to Gemini-specific
        if model_tier == "large":
            extra_args_env = os.environ.get(
                "GAI_LLM_LARGE_ARGS", os.environ.get("GAI_BIG_GEMINI_ARGS")
            )
        else:
            extra_args_env = os.environ.get(
                "GAI_LLM_SMALL_ARGS", os.environ.get("GAI_LITTLE_GEMINI_ARGS")
            )

        if extra_args_env:
            for arg in extra_args_env.split():
                base_args.append(arg)

        # Start the process and stream output in real-time with timer
        timer_context = (
            gemini_timer("Waiting for Gemini") if not suppress_output else None
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
            error_content = f"Error running gemini command (exit code {return_code})"
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
        """Run the Gemini CLI subprocess.

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

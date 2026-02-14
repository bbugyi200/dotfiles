"""Gemini LLM provider implementation.

Extracts only the Gemini-specific subprocess logic from the old
GeminiCommandWrapper.invoke() method.
"""

import os
import select
import subprocess
import sys

from rich_utils import gemini_timer

from .base import LLMProvider
from .types import ModelTier


def stream_process_output(
    process: subprocess.Popen[str],
    suppress_output: bool = False,
) -> tuple[str, str, int]:
    """Stream stdout and stderr from a process in real-time.

    Args:
        process: The subprocess.Popen process to stream from.
        suppress_output: If True, don't print output to console.

    Returns:
        Tuple of (stdout_content, stderr_content, return_code).
    """
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    # Set stdout and stderr to non-blocking mode
    if process.stdout:
        os.set_blocking(process.stdout.fileno(), False)
    if process.stderr:
        os.set_blocking(process.stderr.fileno(), False)

    while True:
        # Use select to wait for data on stdout or stderr
        readable: list[object] = []
        if process.stdout:
            readable.append(process.stdout)
        if process.stderr:
            readable.append(process.stderr)

        if not readable:
            break

        ready, _, _ = select.select(readable, [], [], 0.1)

        # Read from stdout
        if process.stdout and process.stdout in ready:
            line = process.stdout.readline()
            if line:
                stdout_lines.append(line)
                if not suppress_output:
                    print(line, end="", flush=True)

        # Read from stderr
        if process.stderr and process.stderr in ready:
            line = process.stderr.readline()
            if line:
                stderr_lines.append(line)
                if not suppress_output:
                    print(line, end="", file=sys.stderr, flush=True)

        # Check if process has finished
        if process.poll() is not None:
            # Read any remaining output
            if process.stdout:
                for line in process.stdout:
                    stdout_lines.append(line)
                    if not suppress_output:
                        print(line, end="", flush=True)
            if process.stderr:
                for line in process.stderr:
                    stderr_lines.append(line)
                    if not suppress_output:
                        print(line, end="", file=sys.stderr, flush=True)
            break

    return_code = process.wait()
    stdout_content = "".join(stdout_lines)
    stderr_content = "".join(stderr_lines)

    return stdout_content, stderr_content, return_code


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
        if model_tier == "large":
            extra_args_env = os.environ.get("GAI_BIG_GEMINI_ARGS")
        else:
            extra_args_env = os.environ.get("GAI_LITTLE_GEMINI_ARGS")

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

"""Gemini CLI LLM provider implementation."""

import os
import select
import subprocess
import sys

from rich_utils import gemini_timer

from .base import LLMProvider
from .types import LLMInvocationError, ModelSize

_GEMINI_CLI_PATH = "/google/bin/releases/gemini-cli/tools/gemini"


def _stream_process_output(
    process: subprocess.Popen[str], suppress_output: bool = False
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

    if process.stdout:
        os.set_blocking(process.stdout.fileno(), False)
    if process.stderr:
        os.set_blocking(process.stderr.fileno(), False)

    while True:
        readable = []
        if process.stdout:
            readable.append(process.stdout)
        if process.stderr:
            readable.append(process.stderr)

        if not readable:
            break

        ready, _, _ = select.select(readable, [], [], 0.1)

        if process.stdout and process.stdout in ready:
            line = process.stdout.readline()
            if line:
                stdout_lines.append(line)
                if not suppress_output:
                    print(line, end="", flush=True)

        if process.stderr and process.stderr in ready:
            line = process.stderr.readline()
            if line:
                stderr_lines.append(line)
                if not suppress_output:
                    print(line, end="", file=sys.stderr, flush=True)

        if process.poll() is not None:
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
    """LLM provider that invokes the Gemini CLI."""

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "gemini"

    def invoke_llm(
        self,
        query: str,
        *,
        model_size: ModelSize,
        suppress_output: bool = False,
    ) -> str:
        """Invoke Gemini CLI with the given query.

        Args:
            query: The preprocessed prompt text.
            model_size: Which model tier to use ("little" or "big").
            suppress_output: If True, suppress streaming output to console.

        Returns:
            The stripped response text from Gemini.

        Raises:
            LLMInvocationError: If the Gemini CLI exits with a non-zero code.
        """
        base_args = [_GEMINI_CLI_PATH, "--yolo"]

        if model_size == "big":
            extra_args_env = os.environ.get("GAI_BIG_GEMINI_ARGS")
        else:
            extra_args_env = os.environ.get("GAI_LITTLE_GEMINI_ARGS")

        if extra_args_env:
            for arg in extra_args_env.split():
                base_args.append(arg)

        timer_context = (
            gemini_timer("Waiting for Gemini") if not suppress_output else None
        )

        if timer_context:
            with timer_context:
                response_content, stderr_content, return_code = self._run_process(
                    base_args, query, suppress_output
                )
                print()
        else:
            response_content, stderr_content, return_code = self._run_process(
                base_args, query, suppress_output
            )

        if return_code != 0:
            error_content = f"Error running gemini command (exit code {return_code})"
            if stderr_content:
                error_content += f": {stderr_content.strip()}"
            raise LLMInvocationError(error_content)

        return response_content.strip()

    @staticmethod
    def _run_process(
        args: list[str], query: str, suppress_output: bool
    ) -> tuple[str, str, int]:
        """Start a subprocess and stream its output.

        Args:
            args: Command-line arguments for the subprocess.
            query: Text to write to the process stdin.
            suppress_output: If True, suppress streaming output.

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

        if process.stdin:
            process.stdin.write(query)
            process.stdin.close()

        return _stream_process_output(process, suppress_output=suppress_output)

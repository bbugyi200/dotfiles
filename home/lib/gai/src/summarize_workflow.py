"""Workflow for summarizing files using Gemini AI."""

import sys
from typing import NoReturn

from gemini_wrapper import invoke_agent
from shared_utils import ensure_str_content
from workflow_base import BaseWorkflow


def _build_summarize_prompt(target_file: str, usage: str) -> str:
    """Build the summarization prompt.

    Args:
        target_file: Path to the file to summarize.
        usage: Description of how the summary will be used.

    Returns:
        The formatted prompt string.
    """
    return f"""Can you help me summarize the @{target_file} file in <=30 words (preferably <=25 or even <=15 words)? This summary will be used as {usage}.

IMPORTANT: Output ONLY the summary itself, with no additional text, prefixes, or explanations."""


def _extract_summary(response_content: str) -> str:
    """Extract and validate the summary from the response.

    Strips any extra whitespace and validates word count.

    Args:
        response_content: The raw response from the AI.

    Returns:
        The cleaned summary text.
    """
    # Clean up the response
    summary = response_content.strip()

    # Remove common preamble patterns
    preamble_patterns = [
        "Here is the summary:",
        "Here's the summary:",
        "Summary:",
        "The summary is:",
    ]
    for pattern in preamble_patterns:
        if summary.lower().startswith(pattern.lower()):
            summary = summary[len(pattern) :].strip()

    # Remove quotes if the entire response is quoted
    if summary.startswith('"') and summary.endswith('"'):
        summary = summary[1:-1]
    if summary.startswith("'") and summary.endswith("'"):
        summary = summary[1:-1]

    return summary.strip()


class SummarizeWorkflow(BaseWorkflow):
    """A workflow for summarizing files in <=30 words."""

    def __init__(
        self,
        target_file: str,
        usage: str,
        suppress_output: bool = False,
    ) -> None:
        """Initialize the summarize workflow.

        Args:
            target_file: Path to the file to summarize.
            usage: Description of how the summary will be used.
            suppress_output: If True, suppress console output (for background use).
        """
        self.target_file = target_file
        self.usage = usage
        self.suppress_output = suppress_output
        self.summary: str | None = None

    @property
    def name(self) -> str:
        return "summarize"

    @property
    def description(self) -> str:
        return "Summarize a file in <=30 words"

    def run(self) -> bool:
        """Run the summarize workflow.

        Returns:
            True if successful, False otherwise.
        """
        # Build the prompt
        prompt = _build_summarize_prompt(self.target_file, self.usage)

        # Call Gemini with large model for quality
        response = invoke_agent(
            prompt,
            agent_type="summarize",
            model_size="big",
            suppress_output=self.suppress_output,
            workflow="summarize",
        )

        # Extract and store the summary
        response_content = ensure_str_content(response.content)
        self.summary = _extract_summary(response_content)

        return bool(self.summary)


def main() -> NoReturn:
    """Main entry point for the summarize workflow."""
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <target_file> <usage>", file=sys.stderr)
        sys.exit(1)

    target_file = sys.argv[1]
    usage = sys.argv[2]

    workflow = SummarizeWorkflow(target_file=target_file, usage=usage)
    success = workflow.run()

    if success and workflow.summary:
        print(workflow.summary)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

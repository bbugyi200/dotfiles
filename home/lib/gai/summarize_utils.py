"""Utility functions for summarizing files."""

from summarize_workflow import SummarizeWorkflow


def get_file_summary(
    target_file: str,
    usage: str,
    fallback: str = "Operation completed",
) -> str:
    """Get a summary of a file, with fallback on failure.

    This is a convenience wrapper around SummarizeWorkflow for use in
    contexts where a summary is optional and a fallback is acceptable.

    Args:
        target_file: Path to the file to summarize.
        usage: Description of how the summary will be used.
        fallback: Fallback text to use if summarization fails.

    Returns:
        The summary (<=20 words) or fallback text.
    """
    try:
        workflow = SummarizeWorkflow(
            target_file=target_file,
            usage=usage,
            suppress_output=True,
        )
        if workflow.run() and workflow.summary:
            return workflow.summary
    except Exception:
        pass
    return fallback

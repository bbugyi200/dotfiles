"""Functions for formatting CL descriptions."""


def format_cl_description(file_path: str, project: str, bug: str) -> None:
    """Format the CL description file with project tag and metadata.

    Args:
        file_path: Path to the file containing the CL description.
        project: Project name to prepend to the description.
        bug: Bug number to include in metadata.
    """
    # Read the original content
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Write the formatted content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"[{project}] {content}\n")
        f.write("\n")
        f.write("AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT\n")
        f.write(f"BUG={bug}\n")
        f.write("MARKDOWN=true\n")
        f.write("R=startblock\n")
        f.write("STARTBLOCK_AUTOSUBMIT=yes\n")
        f.write("WANT_LGTM=all\n")

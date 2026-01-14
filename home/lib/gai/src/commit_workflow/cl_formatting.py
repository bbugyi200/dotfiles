"""Functions for formatting CL descriptions."""


def format_cl_description(
    file_path: str,
    project: str,
    bug: str | None = None,
    fixed_bug: str | None = None,
) -> None:
    """Format the CL description file with project tag and metadata.

    Args:
        file_path: Path to the file containing the CL description.
        project: Project name to prepend to the description.
        bug: Bug number for BUG= tag. Mutually exclusive with fixed_bug.
        fixed_bug: Bug number for FIXED= tag. Mutually exclusive with bug.
    """
    # Read the original content
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Write the formatted content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"[{project}] {content}\n")
        f.write("\n")
        f.write("AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT\n")
        # Write FIXED= or BUG= tag (mutually exclusive)
        if fixed_bug:
            f.write(f"FIXED={fixed_bug}\n")
        elif bug:
            f.write(f"BUG={bug}\n")
        f.write("MARKDOWN=true\n")
        f.write("R=startblock\n")
        f.write("STARTBLOCK_AUTOSUBMIT=yes\n")
        f.write("WANT_LGTM=all\n")

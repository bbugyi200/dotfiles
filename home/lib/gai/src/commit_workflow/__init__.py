"""Workflow for creating Mercurial commits with formatted CL descriptions."""

import sys
from typing import NoReturn

from .workflow import CommitWorkflow

# Public API
__all__ = [
    "CommitWorkflow",
    "main",
]


def main() -> NoReturn:
    """Main entry point for the commit workflow (standalone execution)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Create a Mercurial commit with formatted CL description and metadata tags."
    )
    parser.add_argument(
        "cl_name",
        help='CL name to use for the commit (e.g., "baz_feature"). The project name '
        'will be automatically prepended if not already present (e.g., "foobar_baz_feature").',
    )
    parser.add_argument(
        "file_path",
        nargs="?",
        help="Path to the file containing the CL description. "
        "If not provided, vim will be opened to write the commit message.",
    )
    parser.add_argument(
        "-b",
        "--bug",
        help="Bug number to include in the metadata tags (e.g., '12345'). "
        "Defaults to the output of the 'branch_bug' command.",
    )
    parser.add_argument(
        "-p",
        "--project",
        help="Project name to prepend to the CL description (e.g., 'foobar'). "
        "Defaults to the output of the 'workspace_name' command.",
    )

    args = parser.parse_args()

    workflow = CommitWorkflow(
        cl_name=args.cl_name,
        file_path=args.file_path,
        bug=args.bug,
        project=args.project,
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

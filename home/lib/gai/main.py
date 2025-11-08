import argparse
import sys
from typing import NoReturn

from create_project_workflow import CreateProjectWorkflow
from crs_workflow import CrsWorkflow
from fix_tests_workflow.main import FixTestsWorkflow
from new_ez_feature_workflow.main import NewEzFeatureWorkflow
from new_failing_tests_workflow.main import NewFailingTestWorkflow
from new_tdd_feature_workflow.main import NewTddFeatureWorkflow
from review_workflow import ReviewWorkflow
from work_projects_workflow import WorkProjectWorkflow
from workflow_base import BaseWorkflow


def _normalize_spec(spec: str) -> str:
    """
    Normalize the spec format to support both M+N+P and MxN syntax.

    Examples:
    - "2+2+2" -> "2+2+2" (unchanged)
    - "2x3" -> "2+2+2"
    - "1x5" -> "1+1+1+1+1"
    - "3x2" -> "3+3"
    """
    spec = spec.strip()

    # Check if it's MxN format
    if "x" in spec and "+" not in spec:
        try:
            parts = spec.split("x")
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid MxN format '{spec}'. Expected format: MxN where M and N are positive integers"
                )

            agents_per_cycle = int(parts[0].strip())
            num_cycles = int(parts[1].strip())

            if agents_per_cycle <= 0 or num_cycles <= 0:
                raise ValueError("Both M and N in MxN format must be positive integers")

            # Convert to M+M+...+M format
            normalized = "+".join([str(agents_per_cycle)] * num_cycles)
            return normalized

        except ValueError as e:
            if "invalid literal for int()" in str(e):
                raise ValueError(
                    f"Invalid MxN format '{spec}'. Both M and N must be positive integers"
                ) from e
            raise

    # If it contains '+' or doesn't contain 'x', assume it's already in M+N+P format
    return spec


def _create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="GAI - Google AI LangGraph workflow runner", prog="gai"
    )

    # Top-level subparsers
    top_level_subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True
    )

    # Create 'run' subcommand
    run_parser = top_level_subparsers.add_parser("run", help="Run a workflow")

    # Workflow subparsers under 'run'
    subparsers = run_parser.add_subparsers(
        dest="workflow", help="Available workflows", required=True
    )

    # fix-tests subcommand
    fix_tests_parser = subparsers.add_parser(
        "fix-tests",
        help="Fix failing tests using planning, editor, and research agents with persistent blackboards",
    )
    fix_tests_parser.add_argument(
        "test_cmd", help="Test command that produces the test failure"
    )
    fix_tests_parser.add_argument(
        "test_output_file", help="Path to the file containing test failure output"
    )
    fix_tests_parser.add_argument(
        "-u",
        "--user-instructions-file",
        help="Optional path to a file to copy as the initial user_instructions.md",
    )
    fix_tests_parser.add_argument(
        "-m",
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of fix iterations before giving up (default: 10)",
    )
    fix_tests_parser.add_argument(
        "-q",
        "--clquery",
        help="Optional query for CLs/PRs to run 'clsurf a:me is:submitted <QUERY>' command and analyze previous work",
    )
    fix_tests_parser.add_argument(
        "-r",
        "--initial-research-file",
        help="Optional path to a file containing initial research to use instead of running research agents",
    )
    fix_tests_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the planner agent prompt",
    )

    # create-project subcommand
    create_project_parser = subparsers.add_parser(
        "create-project",
        help="Create a project plan with proposed CLs based on design documents and prior work",
    )
    create_project_parser.add_argument("bug_id", help="Bug ID to track this project")
    create_project_parser.add_argument(
        "clquery", help="Critique query for clsurf to analyze prior work"
    )
    create_project_parser.add_argument(
        "design_docs_dir",
        help="Directory containing markdown design documents",
    )
    create_project_parser.add_argument(
        "filename",
        help="Filename (basename only, without .md extension) for the project file to be created in ~/.gai/projects/. This will also be used as the NAME field in all ChangeSpecs.",
    )

    # new-failing-tests subcommand
    new_failing_tests_parser = subparsers.add_parser(
        "new-failing-tests",
        help="Add failing tests using TDD - adds failing tests before implementing the feature",
    )
    new_failing_tests_parser.add_argument(
        "project_name",
        help="Name of the project (used for clsurf query and log message prefix)",
    )
    new_failing_tests_parser.add_argument(
        "design_docs_dir",
        help="Directory containing markdown design documents for architectural context",
    )

    # new-tdd-feature subcommand
    new_tdd_feature_parser = subparsers.add_parser(
        "new-tdd-feature",
        help="Implement new features using TDD based on failing tests created by new-failing-tests workflow",
    )
    new_tdd_feature_parser.add_argument(
        "test_output_file",
        help="Path to the test output file from new-failing-tests workflow",
    )
    new_tdd_feature_parser.add_argument(
        "-t",
        "--test-cmd",
        help="Optional test command to run (auto-detected if not provided)",
    )
    new_tdd_feature_parser.add_argument(
        "--test-targets",
        help="Space-separated bazel/blaze test targets (e.g., '//foo:fuzz //bar/baz:buzz')",
    )
    new_tdd_feature_parser.add_argument(
        "-u",
        "--user-instructions-file",
        help="Optional path to a file containing additional instructions for the implementation",
    )
    new_tdd_feature_parser.add_argument(
        "-m",
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of implementation iterations before giving up (default: 10)",
    )
    new_tdd_feature_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the agent prompt (defaults to ~/.gai/designs/<PROJECT> if it exists)",
    )

    # new-ez-feature subcommand
    new_ez_feature_parser = subparsers.add_parser(
        "new-ez-feature",
        help="Implement simple changes that do not require tests",
    )
    new_ez_feature_parser.add_argument(
        "project_name",
        help="Name of the project (used for context)",
    )
    new_ez_feature_parser.add_argument(
        "design_docs_dir",
        help="Directory containing markdown design documents",
    )
    new_ez_feature_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the agent prompt (defaults to ~/.gai/designs/<PROJECT> if it exists)",
    )

    # crs subcommand
    subparsers.add_parser(
        "crs",
        help="Address Critique change request comments on a CL",
    )

    # review subcommand
    subparsers.add_parser(
        "review",
        help="Review a CL for anti-patterns and suggest improvements",
    )

    # Add top-level 'work' command to process ProjectSpec files
    work_parser = top_level_subparsers.add_parser(
        "work",
        help="Process all ProjectSpec files in ~/.gai/projects to create CLs until all ChangeSpecs are in unworkable states",
    )
    work_parser.add_argument(
        "-y",
        "--yolo",
        action="store_true",
        help="Skip confirmation prompts and automatically process all eligible ChangeSpecs",
    )
    work_parser.add_argument(
        "-m",
        "--max-changespecs",
        type=int,
        default=None,
        help="Maximum number of ChangeSpecs to process in one run (default: infinity - process all eligible ChangeSpecs)",
    )
    work_parser.add_argument(
        "-i",
        "--include",
        action="append",
        choices=["blocked", "unblocked", "wip"],
        dest="include_filters",
        help="Filter ChangeSpecs by status category (can be specified multiple times). "
        "blocked: Pre-Mailed, Failed to Fix Tests, Failed to Create CL. "
        "unblocked: Not Started, TDD CL Created. "
        "wip: In Progress, Fixing Tests. "
        "Default: include all ChangeSpecs regardless of status.",
    )

    return parser


def main() -> NoReturn:
    parser = _create_parser()
    args = parser.parse_args()

    workflow: BaseWorkflow

    # Handle top-level 'work' command (Process ProjectSpec files)
    if args.command == "work":
        # Validate that -y and -i are not used together
        if args.yolo and args.include_filters:
            parser.error(
                "The -y/--yolo and -i/--include options are mutually exclusive. "
                "YOLO mode automatically processes only 'unblocked' ChangeSpecs."
            )

        # If -y is specified without -i, automatically set to unblocked
        include_filters = args.include_filters
        if args.yolo and not include_filters:
            include_filters = ["unblocked"]

        workflow = WorkProjectWorkflow(
            args.yolo,
            args.max_changespecs,
            include_filters,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)

    # Verify we're using the 'run' command
    if args.command != "run":
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    if args.workflow == "fix-tests":
        workflow = FixTestsWorkflow(
            args.test_cmd,
            args.test_output_file,
            args.user_instructions_file,
            args.max_iterations,
            args.clquery,
            args.initial_research_file,
            args.context_file_directory,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "create-project":
        workflow = CreateProjectWorkflow(
            args.bug_id,
            args.clquery,
            args.design_docs_dir,
            args.filename,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "new-failing-tests":
        # Read ChangeSpec from STDIN
        changespec_text = sys.stdin.read()
        if not changespec_text.strip():
            print("Error: No ChangeSpec provided on STDIN")
            sys.exit(1)

        workflow = NewFailingTestWorkflow(
            args.project_name,
            args.design_docs_dir,
            changespec_text,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "new-tdd-feature":
        workflow = NewTddFeatureWorkflow(
            args.test_output_file,
            args.test_cmd,
            args.test_targets,
            args.user_instructions_file,
            args.max_iterations,
            args.context_file_directory,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "new-ez-feature":
        # Read ChangeSpec from STDIN
        changespec_text = sys.stdin.read()
        if not changespec_text.strip():
            print("Error: No ChangeSpec provided on STDIN")
            sys.exit(1)

        workflow = NewEzFeatureWorkflow(
            args.project_name,
            args.design_docs_dir,
            changespec_text,
            args.context_file_directory,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "crs":
        workflow = CrsWorkflow()
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "review":
        workflow = ReviewWorkflow()
        success = workflow.run()
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)


if __name__ == "__main__":
    main()

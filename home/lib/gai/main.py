import argparse
import sys

from failed_test_research_workflow import FailedTestResearchWorkflow
from failed_test_summary_workflow import FailedTestSummaryWorkflow
from fix_test_workflow import FixTestWorkflow


def create_parser():
    """Create the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="GAI - Google AI LangGraph workflow runner", prog="gai"
    )

    subparsers = parser.add_subparsers(
        dest="workflow", help="Available workflows", required=True
    )

    # fix-test subcommand
    fix_test_parser = subparsers.add_parser(
        "fix-test", help="Fix failing tests using AI agents"
    )
    fix_test_parser.add_argument("test_file_path", help="Path to the test output file")
    fix_test_parser.add_argument(
        "-S",
        "--spec",
        default="2+2+2",
        help="Specification for agent cycles in format M[+N[+P[+...]]] (default: 2+2+2)",
    )

    # failed-test-research subcommand
    failed_test_research_parser = subparsers.add_parser(
        "failed-test-research",
        help="Conduct research on failed test fixes to discover new resources and insights",
    )
    failed_test_research_parser.add_argument(
        "artifacts_dir",
        help="Path to the artifacts directory from a failed fix-test run",
    )

    # failed-test-summary subcommand
    fix_test_yaqs_parser = subparsers.add_parser(
        "failed-test-summary",
        help="Generate YAQs questions from failed fix-test workflows",
    )
    fix_test_yaqs_parser.add_argument(
        "artifacts_dir",
        help="Path to the artifacts directory from a failed fix-test run",
    )

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.workflow == "fix-test":
        workflow = FixTestWorkflow(args.test_file_path, args.spec)
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "failed-test-research":
        workflow = FailedTestResearchWorkflow(args.artifacts_dir)
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "failed-test-summary":
        workflow = FailedTestSummaryWorkflow(args.artifacts_dir)
        success = workflow.run()
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)


if __name__ == "__main__":
    main()

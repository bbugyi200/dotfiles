import argparse
import sys

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

    # fix-test-yaqs subcommand
    fix_test_yaqs_parser = subparsers.add_parser(
        "fix-test-yaqs", help="Generate YAQs questions from failed fix-test workflows"
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
        workflow = FixTestWorkflow(args.test_file_path)
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "fix-test-yaqs":
        workflow = FailedTestSummaryWorkflow(args.artifacts_dir)
        success = workflow.run()
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)


if __name__ == "__main__":
    main()

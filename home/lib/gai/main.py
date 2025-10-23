import argparse
import sys

from add_tests_workflow import AddTestsWorkflow
from failed_test_research_workflow import FailedTestResearchWorkflow
from failed_test_summary_workflow import FailedTestSummaryWorkflow
from fix_test_workflow import FixTestWorkflow


def normalize_spec(spec: str) -> str:
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
                )
            raise

    # If it contains '+' or doesn't contain 'x', assume it's already in M+N+P format
    return spec


def create_parser():
    """Create the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="GAI - Google AI LangGraph workflow runner", prog="gai"
    )

    subparsers = parser.add_subparsers(
        dest="workflow", help="Available workflows", required=True
    )

    # add-tests subcommand
    add_tests_parser = subparsers.add_parser(
        "add-tests", help="Add new tests to existing test files and verify they pass"
    )
    add_tests_parser.add_argument(
        "test_file", help="Path to the test file where new tests will be added"
    )
    add_tests_parser.add_argument(
        "test_cmd", help="Test command to run to verify the tests"
    )
    add_tests_parser.add_argument(
        "-q",
        "--query",
        help="Optional query to add to the prompt for test generation",
    )
    add_tests_parser.add_argument(
        "-S",
        "--spec",
        default="2+2+2",
        help="Specification for agent cycles (used by fix-test if needed). Formats: M[+N[+P[+...]]] or MxN. Examples: '2+2+2', '2x3', '1+2+3+4', '1x5' (default: 2+2+2)",
    )
    add_tests_parser.add_argument(
        "-T",
        "--num-of-test-runs",
        type=int,
        default=1,
        help="Maximum number of test runs allowed per agent (default: 1)",
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
        help="Specification for agent cycles. Formats: M[+N[+P[+...]]] or MxN. Examples: '2+2+2', '2x3', '1+2+3+4', '1x5' (default: 2+2+2)",
    )
    fix_test_parser.add_argument(
        "-T",
        "--num-of-test-runs",
        type=int,
        default=1,
        help="Maximum number of test runs allowed per agent (default: 1)",
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
    failed_test_summary_parser = subparsers.add_parser(
        "failed-test-summary",
        help="Generate YAQs questions from failed fix-test workflows",
    )
    failed_test_summary_parser.add_argument(
        "artifacts_dir",
        help="Path to the artifacts directory from a failed fix-test run",
    )

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.workflow == "add-tests":
        try:
            normalized_spec = normalize_spec(args.spec)
            workflow = AddTestsWorkflow(
                args.test_file,
                args.test_cmd,
                args.query,
                normalized_spec,
                args.num_of_test_runs,
            )
            success = workflow.run()
            sys.exit(0 if success else 1)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.workflow == "fix-test":
        try:
            normalized_spec = normalize_spec(args.spec)
            workflow = FixTestWorkflow(
                args.test_file_path, normalized_spec, args.num_of_test_runs
            )
            success = workflow.run()
            sys.exit(0 if success else 1)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
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

import argparse
import sys

from add_tests_workflow import AddTestsWorkflow
from fix_tests_workflow.main import FixTestsWorkflow


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

    # fix-test subcommand (DEPRECATED)
    fix_test_parser = subparsers.add_parser(
        "fix-test", help="[DEPRECATED] Fix failing tests using AI agents"
    )
    fix_test_parser.add_argument("test_file_path", help="Path to the test output file")
    fix_test_parser.add_argument(
        "-S",
        "--spec",
        default="2+2+2",
        help="[DEPRECATED] Specification for agent cycles. Formats: M[+N[+P[+...]]] or MxN. Examples: '2+2+2', '2x3', '1+2+3+4', '1x5' (default: 2+2+2)",
    )
    fix_test_parser.add_argument(
        "-T",
        "--num-of-test-runs",
        type=int,
        default=1,
        help="[DEPRECATED] Maximum number of test runs allowed per agent (default: 1)",
    )

    # failed-test-research subcommand (DEPRECATED)
    failed_test_research_parser = subparsers.add_parser(
        "failed-test-research",
        help="[DEPRECATED] Conduct research on failed test fixes to discover new resources and insights",
    )
    failed_test_research_parser.add_argument(
        "artifacts_dir",
        help="Path to the artifacts directory from a failed fix-test run",
    )

    # failed-test-summary subcommand (DEPRECATED)
    failed_test_summary_parser = subparsers.add_parser(
        "failed-test-summary",
        help="[DEPRECATED] Generate YAQs questions from failed fix-test workflows",
    )
    failed_test_summary_parser.add_argument(
        "artifacts_dir",
        help="Path to the artifacts directory from a failed fix-test run",
    )

    # fix-tests subcommand (new workflow)
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
        "-b",
        "--blackboard-file",
        help="Optional path to a file to copy as the initial blackboard.md",
    )
    fix_tests_parser.add_argument(
        "-m",
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of fix iterations before giving up (default: 10)",
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
    elif args.workflow == "fix-tests":
        workflow = FixTestsWorkflow(
            args.test_cmd,
            args.test_output_file,
            args.blackboard_file,
            args.max_iterations,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)


if __name__ == "__main__":
    main()

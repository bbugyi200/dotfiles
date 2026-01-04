import os

from gai_utils import run_shell_command, run_shell_command_with_input

from ..state import (
    FixTestsState,
)


def run_test(state: FixTestsState) -> FixTestsState:
    """Run the actual test command and check if it passes."""
    editor_iteration = state["current_iteration"] - 1
    test_cmd = state["test_cmd"]
    print(f"Running test command (editor iteration {editor_iteration}): {test_cmd}")
    artifacts_dir = state["artifacts_dir"]
    print(f"Executing: {test_cmd}")
    result = run_shell_command(test_cmd, capture_output=True)
    test_passed = result.returncode == 0
    if test_passed:
        print("✅ Test PASSED!")
    else:
        print("❌ Test failed")
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"Test stderr: {result.stderr}")
    trimmed_stdout = result.stdout
    if result.stdout:
        try:
            trim_result = run_shell_command_with_input(
                "trim_test_output", result.stdout, capture_output=True
            )
            if trim_result.returncode == 0:
                trimmed_stdout = trim_result.stdout
            else:
                print(
                    "Warning: trim_test_output command failed for test output, using original"
                )
        except Exception as e:
            print(f"Warning: Could not trim test output: {e}")
    test_output_content = f"Command: {test_cmd}\nReturn code: {result.returncode}\nSTDOUT:\n{trimmed_stdout}\nSTDERR:\n{result.stderr}\n"
    iter_test_output_path = os.path.join(
        artifacts_dir, f"editor_iter_{editor_iteration}_test_output.txt"
    )
    with open(iter_test_output_path, "w") as f:
        f.write(test_output_content)
    return {**state, "test_passed": test_passed}

"""Tests for hook wrapper script retry logic.

Tests the bash wrapper script that's generated in execution.py to verify
retry behavior for transient errors like 'Per user memory limit reached'.
"""

import os
import subprocess
import tempfile

# Test with fast delays to speed up tests
_TEST_RETRY_DELAY = 1  # 1 second instead of 60


def _create_test_wrapper_script(
    command: str, retry_delay: int = _TEST_RETRY_DELAY
) -> str:
    """Create a wrapper script with the retry logic for testing.

    Uses a shorter retry delay than production for faster tests.
    """
    return f"""#!/bin/bash

# Retry configuration
MAX_RETRIES=3
RETRY_DELAY={retry_delay}

# Patterns that trigger retry (grep -E format)
RETRIABLE_PATTERNS=(
    "Per user memory limit reached"
)

echo "=== HOOK COMMAND ==="
echo "{command}"
echo "===================="
echo ""

# Build grep pattern from array
build_pattern() {{
    local IFS='|'
    echo "${{RETRIABLE_PATTERNS[*]}}"
}}

# Check if output contains retriable error
is_retriable() {{
    local output_file="$1"
    local pattern
    pattern=$(build_pattern)
    grep -qE "$pattern" "$output_file" 2>/dev/null
}}

# Execute command with retry logic
attempt=1
while [ $attempt -le $MAX_RETRIES ]; do
    tmp_output=$(mktemp)
    trap "rm -f '$tmp_output'" EXIT

    ( {command} ) > "$tmp_output" 2>&1
    exit_code=$?

    if [ $exit_code -ne 0 ] && [ $attempt -lt $MAX_RETRIES ] && is_retriable "$tmp_output"; then
        echo "=== RETRY ATTEMPT $attempt/$MAX_RETRIES ==="
        echo "Detected retriable error. Waiting ${{RETRY_DELAY}}s before retry..."
        cat "$tmp_output"
        echo ""
        echo "=== WAITING ${{RETRY_DELAY}}s ==="
        rm -f "$tmp_output"
        sleep $RETRY_DELAY
        attempt=$((attempt + 1))
    else
        if [ $attempt -gt 1 ]; then
            echo "=== FINAL ATTEMPT ($attempt/$MAX_RETRIES) ==="
        fi
        cat "$tmp_output"
        rm -f "$tmp_output"
        break
    fi
done

echo ""
# Log end timestamp in YYmmdd_HHMMSS format (America/New_York timezone)
end_timestamp=$(TZ="America/New_York" date +"%y%m%d_%H%M%S")
echo "===HOOK_COMPLETE=== END_TIMESTAMP: $end_timestamp EXIT_CODE: $exit_code"
sync
exit $exit_code
"""


def _run_wrapper_script(script_content: str) -> tuple[int, str]:
    """Run a wrapper script and return exit code and output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write(script_content)
        script_path = f.name

    try:
        os.chmod(script_path, 0o755)
        result = subprocess.run(
            [script_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout + result.stderr
    finally:
        os.unlink(script_path)


def test_wrapper_success_no_retry() -> None:
    """Command succeeds on first try - no retry output shown."""
    script = _create_test_wrapper_script("echo 'Success!'")
    exit_code, output = _run_wrapper_script(script)

    assert exit_code == 0
    assert "Success!" in output
    assert "RETRY ATTEMPT" not in output
    assert "FINAL ATTEMPT" not in output
    assert "===HOOK_COMPLETE===" in output
    assert "EXIT_CODE: 0" in output


def test_wrapper_nonretriable_failure() -> None:
    """Command fails with non-retriable error - no retry, immediate failure."""
    script = _create_test_wrapper_script("echo 'Some random error' && exit 1")
    exit_code, output = _run_wrapper_script(script)

    assert exit_code == 1
    assert "Some random error" in output
    assert "RETRY ATTEMPT" not in output
    assert "===HOOK_COMPLETE===" in output
    assert "EXIT_CODE: 1" in output


def test_wrapper_retry_then_success() -> None:
    """Command fails with retriable error, then succeeds on retry."""
    # Create a script that fails first time with retriable error, succeeds second time
    # Uses a counter file to track attempts
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        counter_file = f.name
        f.write("0")

    try:
        # Inner command: reads counter, if 0 fails with retriable error, else succeeds
        inner_cmd = (
            f"count=$(cat {counter_file}); "
            f"echo $((count + 1)) > {counter_file}; "
            f"if [ $count -eq 0 ]; then "
            f"echo 'ERROR: Per user memory limit reached' && exit 1; "
            f"else echo 'Success on retry!' && exit 0; fi"
        )
        script = _create_test_wrapper_script(inner_cmd)
        exit_code, output = _run_wrapper_script(script)

        assert exit_code == 0
        assert "Per user memory limit reached" in output
        assert "RETRY ATTEMPT 1/3" in output
        assert "Detected retriable error" in output
        assert "FINAL ATTEMPT (2/3)" in output
        assert "Success on retry!" in output
        assert "===HOOK_COMPLETE===" in output
        assert "EXIT_CODE: 0" in output
    finally:
        os.unlink(counter_file)


def test_wrapper_all_retries_exhausted() -> None:
    """Command fails with retriable error on all attempts."""
    # Always fails with retriable error
    inner_cmd = "echo 'ERROR: Per user memory limit reached' && exit 1"
    script = _create_test_wrapper_script(inner_cmd)
    exit_code, output = _run_wrapper_script(script)

    assert exit_code == 1
    assert "Per user memory limit reached" in output
    assert "RETRY ATTEMPT 1/3" in output
    assert "RETRY ATTEMPT 2/3" in output
    assert "FINAL ATTEMPT (3/3)" in output
    assert "===HOOK_COMPLETE===" in output
    assert "EXIT_CODE: 1" in output


def test_wrapper_retry_on_second_attempt() -> None:
    """Command fails twice with retriable error, succeeds on third attempt."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        counter_file = f.name
        f.write("0")

    try:
        # Fails on attempts 1 and 2, succeeds on attempt 3
        inner_cmd = (
            f"count=$(cat {counter_file}); "
            f"echo $((count + 1)) > {counter_file}; "
            f"if [ $count -lt 2 ]; then "
            f"echo 'ERROR: Per user memory limit reached' && exit 1; "
            f"else echo 'Success on third attempt!' && exit 0; fi"
        )
        script = _create_test_wrapper_script(inner_cmd)
        exit_code, output = _run_wrapper_script(script)

        assert exit_code == 0
        assert "RETRY ATTEMPT 1/3" in output
        assert "RETRY ATTEMPT 2/3" in output
        assert "FINAL ATTEMPT (3/3)" in output
        assert "Success on third attempt!" in output
        assert "EXIT_CODE: 0" in output
    finally:
        os.unlink(counter_file)


def test_wrapper_partial_match_not_retriable() -> None:
    """Error message that partially matches but isn't exact doesn't trigger retry."""
    # "memory limit" without "Per user" prefix shouldn't match
    inner_cmd = "echo 'ERROR: memory limit exceeded' && exit 1"
    script = _create_test_wrapper_script(inner_cmd)
    exit_code, output = _run_wrapper_script(script)

    assert exit_code == 1
    assert "memory limit exceeded" in output
    assert "RETRY ATTEMPT" not in output
    assert "EXIT_CODE: 1" in output

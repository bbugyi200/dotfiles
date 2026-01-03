#!/bin/bash
set -e

# Directory containing this script (the .claude/hooks directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_DIR"

# Collect errors
errors=""

# Run make fix
if ! output=$(make fix 2>&1); then
    errors+="make fix FAILED:\n$output\n\n"
fi

# Run make lint
if ! output=$(make lint 2>&1); then
    errors+="make lint FAILED:\n$output\n\n"
fi

# Run make test
if ! output=$(make test 2>&1); then
    errors+="make test FAILED:\n$output\n\n"
fi

# Run chezmoi apply
if ! output=$(chezmoi apply 2>&1); then
    errors+="chezmoi apply FAILED:\n$output\n\n"
fi

# If any errors occurred, block and report
if [ -n "$errors" ]; then
    echo -e "$errors" >&2
    exit 2  # Exit code 2 blocks Claude and shows stderr
fi

exit 0

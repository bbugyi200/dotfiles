#!/bin/bash
# Setup script to configure git hooks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "Setting up git hooks..."

# Configure git to use .githooks directory
git config core.hooksPath .githooks

# Make sure hooks are executable
chmod +x .githooks/*

echo "✅ Git hooks configured successfully!"
echo ""
echo "Pre-commit hook will now run 'make fix' before each commit."

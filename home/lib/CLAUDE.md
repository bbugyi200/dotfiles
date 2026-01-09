# Python Coding Guidelines

## How to lint/test Python code?

- To run linters for Python code, use the `make lint-python` command.
- To run tests for Python code, use the `make test-python` command.
- The above commands need to be run from the root of the project (from the ~/.local/share/chezmoi/ directory).

## Core Rules

1. **Private functions/methods/classes**: ALWAYS prefix with underscore (`_`)
2. **Type annotations**: ALWAYS annotate ALL function parameters and return types
3. **Import style**: ALWAYS use `from foo import bar` instead of `import foo` then `foo.bar()`
   - ✅ Good: `from rich_utils import print_status, print_workflow_header`
   - ❌ Bad: `import rich_utils` then `rich_utils.print_status(...)`
4. **Shared utilities**: NEVER put single-use functions in shared modules - move them to their only consumer as private
   functions
5. **Private function imports**: NEVER import private functions (prefixed with `_`) across modules - make them public if
   they need to be shared
   - **Exception**: Test files (files with `test_` prefix) MAY import private functions from the modules they are
     testing
   - **Test import requirement**: Test files MUST import private functions directly from their defining module, NOT via
     `__init__.py` re-exports
     - ✅ Good: `from mypackage.mymodule import _private_function`
     - ❌ Bad: `from mypackage import _private_function` (via `__init__.py`)
6. **Unused functions**: If a function is flagged as unused by the linter (`executable_unused_pydefs`):
   - If the function is not used anywhere → DELETE it entirely
   - If the function is only used within its own file → Make it private (prefix with `_`)
7. **Large file splitting**: Once a single Python file gets to be >=900 lines long, start thinking about splitting it
   into a Python package with multiple files

## Testing Requirements

**CRITICAL**: Testing is mandatory for large Python projects.

### When Tests Are Required

1. **Project Size Threshold**: Any Python project (e.g., `home/lib/gai`) that exceeds **1000 lines of code** MUST have
   dedicated tests
   - Count includes all `.py` files in the project directory
   - Use `find home/lib/PROJECT -name "*.py" -exec wc -l {} + | tail -1` to check total lines

2. **New Features in Large Projects**: When adding new features to projects that already have tests (e.g.,
   `home/lib/gai`), you MUST:
   - Add corresponding test coverage for the new feature
   - Update existing tests if the feature modifies existing behavior
   - Ensure `make test` passes before completing the task

### Test Coverage Requirements

**CRITICAL**: NEVER let `make test` fail due to low test coverage.

When test coverage drops below the required threshold (typically 40%):

1. **First choice**: Add tests for the new code you just wrote
2. **If that's not ideal** (e.g., UI code that's hard to test): Add meaningful test coverage elsewhere in the codebase
   - Look for untested helper functions, utility functions, or data transformations
   - Focus on adding value with your tests, not just hitting a number
   - Simple functions with clear inputs/outputs are easiest to test

The goal is to maintain or improve coverage with each change. If you add code that's difficult to test (like interactive
UI), compensate by testing other parts of the codebase that need coverage.

**CRITICAL**: NEVER decrease the required test coverage threshold (e.g., in `pyproject.toml` `--cov-fail-under`
setting). Always maintain or increase the threshold. If you cannot meet the current threshold, add more tests instead of
lowering the bar.

### Test Guidelines

- Place tests in a `test/` directory within the project
- Name test files with `test_` prefix (e.g., `test_main.py`)
- Use **pytest** for Python tests
- Use **global `test_*` functions** (NOT nested in classes) in most cases
  - Classes should only be used for sharing fixtures or grouping highly related tests
  - Keep tests simple and flat by default
- Aim for meaningful test coverage, not just line coverage
- Test both happy paths and error cases
- Always add type annotations to test functions (return type should be `-> None`)

### Example

```python
# home/lib/gai/test/test_main.py
import pytest
from gai.main import normalize_spec


def test_normalize_spec_plus_format_unchanged() -> None:
    """Test that plus format is preserved."""
    assert normalize_spec("3+2") == "3+2"


def test_normalize_spec_invalid_format() -> None:
    """Test that invalid formats raise ValueError."""
    with pytest.raises(ValueError):
        normalize_spec("invalid")
```

## Examples

### Private Functions

```python
# ✅ Good
def _create_boxed_header(title: str) -> str:
    return f"=== {title} ==="

# ❌ Bad
def create_boxed_header(title):  # Missing underscore and types
    return f"=== {title} ==="
```

### Shared vs Single-Use

```python
# ✅ Good - In the module that uses it
def _read_artifact_file(file_path: str) -> str:
    """Private function used only by this module."""
    with open(file_path) as f:
        return f.read()

# ❌ Bad - In shared_utils.py when only one module uses it
def read_artifact_file(file_path: str) -> str:
    with open(file_path) as f:
        return f.read()
```

### Type Annotations

```python
# ✅ Good
def process_data(items: list[str], max_count: int = 100) -> dict[str, int]:
    return {}

# ❌ Bad
def process_data(items, max_count=100):
    return {}
```

## File Size Limits

**CRITICAL**: When a Python file exceeds 750 lines, break it into a package with multiple modules. NEVER compress
docstrings to fit the limit.

Group related functions logically, update `__init__.py` for backward compatibility, and split test files along the same
module boundaries.
